"""Subtitle files to readable text.

Three formats matter, because they are what yt-dlp hands back: WebVTT, SubRip,
and YouTube's own `json3`. They all carry the same words wrapped in different
amounts of timing.

The part that actually needs care is **rolling captions**. YouTube's automatic
captions are written to be read on a screen two lines at a time, so each cue
repeats the tail of the one before it and adds a few words:

    00:00:00.030 --> 00:00:02.669
    so today we're<00:00:00.719><c> making</c><00:00:01.020><c> a</c>

    00:00:02.669 --> 00:00:02.679
    so today we're making a carbonara

    00:00:02.679 --> 00:00:05.099
    so today we're making a carbonara
    and<00:00:03.120><c> the</c><00:00:03.360><c> first</c>

Concatenated naively that reads "so today we're making a so today we're making
a carbonara so today we're making a carbonara and the first", which is three
times the length and unusable. Dropping a line that repeats what was just
emitted is what makes the result a transcript rather than a stutter.

The output is re-flowed into sentences on purpose. A transcript arrives as
caption-sized fragments, and a wall of four-word lines is not something anyone
will read while checking whether the video really said two teaspoons.
"""

from __future__ import annotations

import html as html_module
import json
import re

# Inline karaoke timing inside a cue: <00:00:00.719> and <c>word</c>.
_INLINE_TAG = re.compile(r"<[^>]*>")
# A cue's timing line. The settings after the timestamps (align, position) are
# part of the same line and go with it.
_TIMING = re.compile(r"^\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*-->")
# SubRip numbers its cues; WebVTT may label them too.
_CUE_NUMBER = re.compile(r"^\d+$")
# WebVTT preamble and metadata we do not want in the text.
_HEADER = re.compile(r"^(WEBVTT|NOTE\b|STYLE\b|REGION\b|Kind:|Language:)", re.I)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class TranscriptError(ValueError):
    """The subtitle content could not be read."""


def _clean_line(line: str) -> str:
    line = _INLINE_TAG.sub("", line)
    line = html_module.unescape(line)
    # Caption files are full of non-breaking spaces used as padding.
    return line.replace(" ", " ").strip()


def _is_noise(line: str) -> bool:
    return (
        not line
        or bool(_TIMING.match(line))
        or bool(_CUE_NUMBER.match(line))
        or bool(_HEADER.match(line))
    )


def from_cue_format(content: str) -> str:
    """WebVTT or SubRip. The two differ only in punctuation we already ignore.

    One function for both because the distinction is a comma versus a full stop
    in the timestamps, and a second near-identical parser would be a second
    place for the rolling-caption fix to be missing.
    """
    kept: list[str] = []
    for raw in content.splitlines():
        line = _clean_line(raw)
        if _is_noise(line):
            continue
        # The rolling-caption fix. Compared case-insensitively because the
        # repeated line is sometimes recapitalised as the cue grows.
        if kept and line.lower() == kept[-1].lower():
            continue
        kept.append(line)
    return reflow(" ".join(kept))


def from_json3(content: str) -> str:
    """YouTube's json3: events, each a list of text segments.

    No rolling repetition here -- events are already sequential -- but there
    are empty events and bare newline segments used for line breaks, and an
    event with no `segs` at all is a timing marker rather than speech.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TranscriptError("That subtitle file isn't valid json3.") from exc

    parts: list[str] = []
    for event in data.get("events") or []:
        for seg in event.get("segs") or []:
            text = seg.get("utf8", "")
            if text.strip():
                parts.append(text.strip())
    return reflow(" ".join(parts))


# yt-dlp names the format; we only read the three worth reading.
READERS = {
    "vtt": from_cue_format,
    "srt": from_cue_format,
    "json3": from_json3,
}


def to_text(content: str, fmt: str) -> str:
    reader = READERS.get(fmt)
    if reader is None:
        raise TranscriptError(
            f"Subtitle format {fmt!r} isn't one CookVault reads "
            f"({', '.join(sorted(READERS))})."
        )
    return reader(content)


def reflow(text: str, width: int = 88) -> str:
    """Caption fragments back into paragraphs.

    Sentences first, because that is the unit a person reads. Auto-captions
    usually have no punctuation at all, in which case there is one enormous
    sentence and the width wrap is the only thing keeping it readable -- which
    is exactly why the wrap exists as well as the split.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    lines: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        current = ""
        for word in sentence.split(" "):
            if current and len(current) + 1 + len(word) > width:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
    return "\n".join(lines)
