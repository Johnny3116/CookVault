"""Importing a recipe from a cooking video.

The spec's first listed pitfall is that caption-only scraping misses 30-50% of
a recipe, so this pulls **both** the description and the spoken transcript and
keeps both. That is the whole point of the feature: the description is usually
where the amounts are written down, and the transcript is where you find the
one the uploader forgot to write down.

What this deliberately does **not** do is pretend it can structure speech.

The description goes through the same line heuristic as a pasted recipe, which
works because recipe-video descriptions are written as lists. A transcript is
prose -- "so you want about two zucchini, an apple, plenty of pepper" -- and
running the line parser over it produces ingredients like "so today we're
making a carbonara and the first thing you need is 200 grams of guanciale".
That is worse than nothing, because it looks like data. So when the description
yields no ingredients, the draft comes back with the title, an empty recipe and
the transcript attached, saying plainly that it could not be structured.

An empty draft that admits it beats a full one that is wrong. Structuring
speech is a model's job, and the seam for that already exists: when the
outbound Agent Zero client lands it fills `extracted_payload` from
`original_text`, and everything downstream is unchanged.

**Only known video hosts are accepted.** Unlike `/import`, which fetches a page
we then parse ourselves, this hands a URL to yt-dlp -- a large extractor that
follows the site's own redirects to wherever the media lives. `check_url` guards
the address we were given; it cannot guard everywhere that library then goes.
An allowlist of the four hosts the spec actually names is a much smaller thing
to reason about, and general web pages already have a path of their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.models import SourceType
from app.services import transcripts
from app.services.recipe_text import parse_recipe_text
from app.services.web_import import SourceFetchError, check_url

# Host -> what kind of source it is. Subdomains are matched by suffix, so
# "m.youtube.com" and "www.tiktok.com" resolve without being listed.
SUPPORTED_HOSTS: dict[str, SourceType] = {
    "youtube.com": SourceType.youtube,
    "youtu.be": SourceType.youtube,
    "tiktok.com": SourceType.tiktok,
    "instagram.com": SourceType.instagram,
}

# json3 first: it has no rolling-caption repetition to undo, so it is the
# format least likely to need the fix in transcripts.py to be perfect.
FORMAT_PREFERENCE = ("json3", "vtt", "srt")

# Subtitles are capped separately from pages: a feature-length auto-caption
# file is large, and none of it is a recipe past a point.
MAX_SUBTITLE_BYTES = 2 * 1024 * 1024


@dataclass
class VideoSource:
    """What came back from the video, before anyone tried to read it."""

    url: str
    source_type: SourceType
    title: str | None = None
    uploader: str | None = None
    description: str = ""
    transcript: str = ""
    # True when the transcript came from machine captions rather than ones a
    # human wrote. It is the same trust gradient as import_method, and a
    # reviewer checking a quantity deserves to know which they are reading.
    transcript_is_automatic: bool = False
    subtitle_language: str | None = None


@dataclass
class VideoImportResult:
    payload: dict
    source: VideoSource
    # "description" when the recipe was read out of the description,
    # "none" when nothing could be structured and the draft is a stub.
    structured_from: str
    note: str
    warnings: list[str] = field(default_factory=list)


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def source_type_for(url: str) -> SourceType | None:
    """The kind of source, or None if this is not a host we accept."""
    host = host_of(url)
    for known, source_type in SUPPORTED_HOSTS.items():
        if host == known or host.endswith(f".{known}"):
            return source_type
    return None


def check_video_url(url: str) -> SourceType:
    """Refuse anything that isn't a public video on a host we know.

    Both checks, in this order: the allowlist is what keeps yt-dlp pointed at
    sites whose behaviour we have thought about, and `check_url` still runs
    because a hostname on the list could still resolve somewhere private
    through a poisoned resolver or a hosts entry.
    """
    source_type = source_type_for(url)
    if source_type is None:
        raise SourceFetchError(
            "Video import handles "
            f"{', '.join(sorted(SUPPORTED_HOSTS))}. "
            "For anything else, use a normal link import."
        )
    check_url(url)
    return source_type


# --------------------------------------------------------------------------
# the network seam
# --------------------------------------------------------------------------


def pick_subtitles(info: dict) -> tuple[dict | None, str | None, bool]:
    """Which subtitle track to read: (track, language, is_automatic).

    Manual subtitles beat automatic ones, because manual captions are what the
    uploader typed and automatic ones are a machine's guess at speech -- and a
    guess about "two teaspoons" is exactly the thing the reviewer is checking.
    English first, then whatever exists, because a transcript in a language
    nobody here reads is still better than none for spotting numbers.
    """
    for source, is_automatic in (
        (info.get("subtitles") or {}, False),
        (info.get("automatic_captions") or {}, True),
    ):
        if not source:
            continue
        languages = sorted(
            source, key=lambda lang: (not lang.startswith("en"), lang)
        )
        for language in languages:
            tracks = source[language] or []
            by_ext = {track.get("ext"): track for track in tracks}
            for ext in FORMAT_PREFERENCE:
                if ext in by_ext:
                    return by_ext[ext], language, is_automatic
    return None, None, False


def fetch_video(url: str) -> VideoSource:
    """Ask yt-dlp about a video and read its captions. Touches the network.

    The one function in this module that does, so a test can replace it and
    everything else stays exercisable -- the same arrangement `/import` uses
    for `fetch_page`.
    """
    import httpx
    import yt_dlp

    source_type = check_video_url(url)

    options = {
        "quiet": True,
        "no_warnings": True,
        # Metadata only. We never want the video itself: this is a cookbook.
        "skip_download": True,
        "writesubtitles": False,
        "noplaylist": True,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp raises a wide family of its own errors
        # Its messages name the site and the reason (private, removed, rate
        # limited), which is more useful to the person pasting the link than
        # anything we could write, so it is passed through rather than hidden
        # behind a generic failure.
        raise SourceFetchError(f"Could not read that video: {exc}") from exc

    if not info:
        raise SourceFetchError("That link didn't resolve to a video.")

    source = VideoSource(
        url=info.get("webpage_url") or url,
        source_type=source_type,
        title=(info.get("title") or "").strip() or None,
        uploader=(info.get("uploader") or info.get("channel") or "").strip() or None,
        description=(info.get("description") or "").strip(),
    )

    track, language, is_automatic = pick_subtitles(info)
    if track and track.get("url"):
        try:
            check_url(track["url"])
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(track["url"])
                response.raise_for_status()
                content = response.text[:MAX_SUBTITLE_BYTES]
            source.transcript = transcripts.to_text(content, track.get("ext", ""))
            source.transcript_is_automatic = is_automatic
            source.subtitle_language = language
        except (httpx.HTTPError, SourceFetchError, transcripts.TranscriptError):
            # A missing transcript is a thinner import, not a failed one. The
            # description alone is often the whole recipe, and refusing the
            # import over the half that is optional would be the wrong trade.
            source.transcript = ""

    return source


# --------------------------------------------------------------------------
# reading what came back
# --------------------------------------------------------------------------


def payload_from_video(source: VideoSource) -> VideoImportResult:
    """Turn a fetched video into a draft payload and an honest note about it."""
    warnings: list[str] = []
    parsed = parse_recipe_text(source.description) if source.description else {}
    ingredients = parsed.get("ingredients") or []

    if ingredients:
        payload = dict(parsed)
        structured_from = "description"
        note = "Ingredients and steps read from the video description."
        if not payload.get("steps"):
            warnings.append(
                "The description listed ingredients but no method -- the steps are "
                "probably only spoken. Check the transcript."
            )
    else:
        # Deliberately empty rather than guessed. See the module docstring:
        # running the line parser over prose produces ingredients that look
        # like data and are not.
        payload = {"ingredients": [], "steps": []}
        structured_from = "none"
        note = (
            "The description didn't contain a recipe, and CookVault doesn't try to "
            "structure speech. The transcript is attached -- fill this in from it."
        )
        warnings.append("Nothing could be structured automatically.")

    # The video's own title, because that is what you will recognise in the
    # queue. The parser's guess at a title came from the description's first
    # line, which is as often a channel tagline as a recipe name.
    payload["title"] = source.title or parsed.get("title") or ""
    payload["source_type"] = source.source_type.value
    payload["source_url"] = source.url

    if not source.transcript:
        warnings.append("No captions were available for this video.")
    elif source.transcript_is_automatic:
        warnings.append(
            "The transcript is automatic captions, not written by the uploader. "
            "Treat spoken numbers as approximate."
        )

    return VideoImportResult(
        payload=payload,
        source=source,
        structured_from=structured_from,
        note=note,
        warnings=warnings,
    )


def original_text(source: VideoSource) -> str:
    """Both halves, kept together and labelled.

    Stored as one field because they are one thing: what the source actually
    said. Labelled because "the description says 200g and the transcript says
    a big handful" is the disagreement worth seeing, and it is invisible if the
    two are merged without saying which is which.
    """
    parts: list[str] = []
    if source.description:
        parts.append(f"--- description ---\n{source.description}")
    if source.transcript:
        kind = "automatic captions" if source.transcript_is_automatic else "captions"
        language = f", {source.subtitle_language}" if source.subtitle_language else ""
        parts.append(f"--- transcript ({kind}{language}) ---\n{source.transcript}")
    return "\n\n".join(parts)
