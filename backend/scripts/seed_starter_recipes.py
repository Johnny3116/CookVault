"""Seed CookVault's review queue with the starter recipe set.

Every recipe goes in as a *draft*, through the same `POST /drafts` door as an
import. Nothing lands in the cookbook until it is promoted from the review
queue, so this script cannot put a recipe in front of you that you haven't
looked at.

Safe to re-run. A recipe is skipped when a saved recipe or a live draft
(draft or ready) already has the same title, compared case-insensitively.
A discarded draft does not count, so discarding one and re-running brings it
back.

Each new draft is validated straight away, which marks it `ready` when it
passes. Validation only reports; it never edits the payload.

Usage, from inside the backend container (the password is already in its env):

    docker compose exec backend python scripts/seed_starter_recipes.py

Or from the host against the published port:

    COOKVAULT_PASSWORD=... python backend/scripts/seed_starter_recipes.py \\
        --base-url http://127.0.0.1:8420

The password is read from the environment only, never a flag, so it doesn't
end up in shell history.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "seed" / "starter_recipes.json"
LIVE_DRAFT_STATUSES = {"draft", "ready"}
PROVENANCE_TITLE = "CookVault starter set"


class SeedError(RuntimeError):
    pass


def load_recipes(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedError(f"Seed file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SeedError(f"Seed file is not valid JSON: {path}: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise SeedError("Seed file must be a non-empty JSON array of recipes.")

    seen: set[str] = set()
    for index, recipe in enumerate(data):
        if not isinstance(recipe, dict):
            raise SeedError(f"Entry {index} is not an object.")
        title = recipe.get("title")
        if not isinstance(title, str) or not title.strip():
            raise SeedError(f"Entry {index} has no title.")
        key = title.strip().lower()
        if key in seen:
            raise SeedError(f"Title {title!r} appears twice in the seed file.")
        seen.add(key)
    return data


def _check(response: httpx.Response, action: str) -> Any:
    if response.status_code >= 400:
        raise SeedError(f"{action} failed: HTTP {response.status_code}: {response.text[:500]}")
    return response.json() if response.content else None


def login(client: httpx.Client) -> None:
    status = _check(client.get("/auth/status"), "Checking auth status")
    if not status.get("auth_required"):
        return
    password = os.environ.get("COOKVAULT_PASSWORD")
    if not password:
        raise SeedError("This CookVault requires a password; set COOKVAULT_PASSWORD.")
    _check(client.post("/auth/login", json={"password": password}), "Logging in")


def existing_titles(client: httpx.Client) -> tuple[set[str], set[str]]:
    recipes = _check(client.get("/recipes"), "Listing recipes")
    drafts = _check(client.get("/drafts"), "Listing drafts")
    saved = {r["title"].strip().lower() for r in recipes if r.get("title")}
    queued = {
        d["title"].strip().lower()
        for d in drafts
        if d.get("title") and d.get("status") in LIVE_DRAFT_STATUSES
    }
    return saved, queued


def seed(client: httpx.Client, recipes: list[dict[str, Any]], dry_run: bool) -> int:
    saved, queued = existing_titles(client)
    created = 0

    for recipe in recipes:
        title = recipe["title"].strip()
        key = title.lower()
        if key in saved:
            print(f"skip   {title}  (already in the cookbook)")
            continue
        if key in queued:
            print(f"skip   {title}  (already waiting in the review queue)")
            continue
        if dry_run:
            print(f"would  {title}")
            continue

        draft = _check(
            client.post(
                "/drafts",
                json={
                    "title": title,
                    "payload": recipe,
                    "provenance": {
                        "source_type": "manual",
                        "import_method": "manual",
                        "source_title": PROVENANCE_TITLE,
                    },
                    "note": "Starter recipe from the seed script. Review, edit and promote, or discard.",
                },
            ),
            f"Creating draft {title!r}",
        )
        result = _check(client.post(f"/drafts/{draft['id']}/validate"), f"Validating {title!r}")
        created += 1
        queued.add(key)

        verdict = "ready" if result.get("ok") else "needs fixes"
        print(f"draft  {title}  ({verdict})")
        for issue in result.get("issues", []):
            print(f"         {issue['severity']}: {issue['field']}: {issue['message']}")

    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--base-url",
        default=os.environ.get("COOKVAULT_API_URL", "http://localhost:8000"),
        help="CookVault API root (default: $COOKVAULT_API_URL or http://localhost:8000)",
    )
    parser.add_argument("--file", type=Path, default=DEFAULT_DATA, help="Seed JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    args = parser.parse_args(argv)

    try:
        recipes = load_recipes(args.file)
        with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=15.0) as client:
            login(client)
            created = seed(client, recipes, args.dry_run)
    except httpx.HTTPError as exc:
        print(f"error: could not reach CookVault at {args.base_url}: {exc}", file=sys.stderr)
        return 1
    except SeedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        print(f"\n{created} new draft(s). Review them at /drafts in CookVault.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
