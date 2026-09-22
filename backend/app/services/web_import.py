"""Fetch a recipe page and get a draft payload out of it.

Most recipe sites publish `schema.org/Recipe` as JSON-LD in the page head,
because Google asks them to. That is structured data the publisher wrote on
purpose, so reading it is *extraction*, not guessing -- no model involved, and
the ingredient amounts are the ones the author typed. When a page has no
JSON-LD we fall back to the text heuristic, which is worse, and lands in a
draft either way.

Two deliberate limitations, stated rather than hidden:

- HTML is picked apart with regexes. There is no HTML parser in the
  dependencies, and pulling one in to find `<script type="application/ld+json">`
  is not worth it while the result is reviewed by a human before it counts.
- Video transcripts are not handled. That needs yt-dlp and Agent Zero, neither
  of which is wired up; `import_method` exists to record the difference when
  they are.
"""

from __future__ import annotations

import html as html_module
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.recipe_text import parse_ingredient_line, parse_recipe_text

# Enough for a recipe page; a 200 MB response is not a recipe.
MAX_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 15.0
# Some sites refuse a bare client. This says what we are rather than pretending
# to be a browser.
USER_AGENT = "CookVault/0.1 (personal recipe importer)"

_SCRIPT_LD = re.compile(
    r"<script[^>]+type\s*=\s*['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
    re.I | re.S,
)
_DROP_BLOCKS = re.compile(r"<(script|style|noscript|template)\b.*?</\1>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_ISO_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", re.I)


class SourceFetchError(RuntimeError):
    """The page could not be fetched, or wasn't something we should fetch."""


def check_url(url: str) -> None:
    """Refuse anything that isn't a public web page, before connecting.

    The server fetches whatever URL it is handed, so without this a typo -- or
    a pasted link from somewhere else -- could make CookVault fetch from inside
    the Tailscale network or from a cloud metadata endpoint and store the reply
    in a draft. A recipe never lives at a private address, so refusing them all
    costs nothing.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SourceFetchError("Only http and https URLs can be imported.")
    if not parsed.hostname:
        raise SourceFetchError("That URL has no host.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise SourceFetchError(f"Could not resolve {parsed.hostname}.") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        # These overlap: Python counts loopback and link-local as private, so
        # those two clauses change nothing today and no test can tell them
        # apart. They stay because this is a security check, and one that
        # leans entirely on another library's definition of "private" is one
        # that regresses silently when that definition moves. is_multicast and
        # is_reserved do add real coverage.
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        ):
            raise SourceFetchError(
                f"{parsed.hostname} resolves to a private address ({address}); "
                "only public recipe pages can be imported."
            )


def fetch_page(url: str) -> str:
    """Fetch a page's HTML. Raises SourceFetchError on anything unusable."""
    check_url(url)
    try:
        with httpx.Client(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SourceFetchError(f"{url} returned {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise SourceFetchError(f"Could not fetch {url}: {exc}") from exc

    if len(response.content) > MAX_BYTES:
        raise SourceFetchError("That page is too large to import.")
    return response.text


def iso_duration_to_minutes(value: Any) -> int | None:
    """`PT1H30M` -> 90. Anything unrecognised -> None rather than a guess."""
    if not isinstance(value, str):
        return None
    match = _ISO_DURATION.match(value.strip())
    if not match:
        return None
    days, hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    total = days * 1440 + hours * 60 + minutes + (1 if seconds and not minutes else 0)
    return total or None


def _iter_nodes(data: Any):
    """Walk JSON-LD, which may be a node, a list, or wrapped in @graph."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _iter_nodes(data["@graph"])


def _is_recipe(node: dict) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, str):
        return node_type.lower() == "recipe"
    if isinstance(node_type, list):
        return any(isinstance(t, str) and t.lower() == "recipe" for t in node_type)
    return False


def extract_jsonld_recipe(page_html: str) -> dict | None:
    """The first schema.org Recipe node in the page, or None."""
    for block in _SCRIPT_LD.findall(page_html):
        try:
            data = json.loads(html_module.unescape(block.strip()))
        except json.JSONDecodeError:
            # One malformed block shouldn't stop us reading the next.
            continue
        for node in _iter_nodes(data):
            if _is_recipe(node):
                return node
    return None


def _text_of(value: Any) -> str:
    """JSON-LD values arrive as strings, dicts, or lists of either."""
    if isinstance(value, str):
        return _strip_html(value).strip()
    if isinstance(value, dict):
        return _text_of(value.get("text") or value.get("name") or "")
    if isinstance(value, list):
        return " ".join(part for part in (_text_of(item) for item in value) if part)
    return ""


def _instruction_texts(value: Any) -> list[str]:
    """Flatten recipeInstructions, which may be prose, a list of steps, or
    HowToSections containing lists of steps."""
    if isinstance(value, str):
        # One prose blob: split on newlines, falling back to sentences.
        text = _strip_html(value)
        parts = [line.strip() for line in text.splitlines() if line.strip()]
        if len(parts) <= 1:
            parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        return parts
    if isinstance(value, dict):
        if value.get("@type") == "HowToSection" and value.get("itemListElement"):
            return _instruction_texts(value["itemListElement"])
        text = _text_of(value)
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_instruction_texts(item))
        return out
    return []


def _first_int(value: Any) -> int | None:
    """recipeYield is "4", "4 servings", or ["4", "4 servings"]."""
    if isinstance(value, list):
        for item in value:
            found = _first_int(item)
            if found is not None:
                return found
        return None
    if isinstance(value, int):
        return value or None
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        return int(match.group()) if match else None
    return None


def _tags(node: dict) -> list[str]:
    raw: list[str] = []
    for key in ("recipeCategory", "recipeCuisine", "keywords"):
        value = node.get(key)
        if isinstance(value, str):
            raw.extend(part.strip() for part in value.split(","))
        elif isinstance(value, list):
            raw.extend(str(part).strip() for part in value if isinstance(part, (str, int)))
    seen: list[str] = []
    for tag in raw:
        cleaned = tag.strip().lower()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen[:12]


def _strip_html(value: str) -> str:
    return html_module.unescape(_TAG.sub(" ", value)).replace("\xa0", " ").strip()


def payload_from_jsonld(node: dict) -> dict:
    """A schema.org Recipe node -> a draft payload.

    Ingredient strings still go through the line parser, because JSON-LD
    publishes them as written ("1 1/2 cups flour"), not as fields.
    """
    ingredients = []
    for line in node.get("recipeIngredient") or node.get("ingredients") or []:
        if not isinstance(line, str):
            continue
        parsed = parse_ingredient_line(_strip_html(line))
        if parsed:
            ingredients.append(parsed)

    steps = [
        {"order": index, "instruction_text": text}
        for index, text in enumerate(_instruction_texts(node.get("recipeInstructions")), start=1)
    ]

    return {
        "title": _text_of(node.get("name")),
        "servings": _first_int(node.get("recipeYield")),
        "prep_time": iso_duration_to_minutes(node.get("prepTime")),
        "cook_time": iso_duration_to_minutes(node.get("cookTime")),
        "tags": _tags(node),
        "cook_methods": [],
        "ingredients": ingredients,
        "steps": steps,
        "alternates": [],
    }


def html_to_text(page_html: str) -> str:
    """Crude readable text, for pages with no JSON-LD at all."""
    without_blocks = _DROP_BLOCKS.sub(" ", page_html)
    with_breaks = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6])[^>]*>", "\n", without_blocks)
    text = _strip_html(with_breaks)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def payload_from_page(page_html: str) -> tuple[dict, str, bool]:
    """Best available reading of a page.

    Returns the draft payload, the source text worth keeping alongside it, and
    whether that came from JSON-LD. The source text is stored separately from
    the payload so the two can be compared later -- that is the whole reason
    provenance has two columns.
    """
    node = extract_jsonld_recipe(page_html)
    if node is not None:
        return payload_from_jsonld(node), json.dumps(node, indent=2, ensure_ascii=False), True

    text = html_to_text(page_html)
    return parse_recipe_text(text), text, False
