"""Reading a cooking video: captions, hosts, and what not to guess at.

Nothing here touches the network. `fetch_video` is replaced wherever a test
needs a video, for the same reason `fetch_page` is in test_import: a test that
depends on a YouTube link staying up fails for reasons that have nothing to do
with this code.

Two claims carry most of the weight. The first is the rolling-caption fix --
without it a transcript reads as a stutter three times its real length. The
second is that when the description holds no recipe, the draft comes back
**empty and says so** rather than full of prose parsed into ingredients.
"""

from __future__ import annotations

import pathlib

import pytest

from app.models import SourceType
from app.services import transcripts, video_import
from app.services.web_import import SourceFetchError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# --------------------------------------------------------------------------
# reading captions
# --------------------------------------------------------------------------


def test_rolling_captions_do_not_stutter():
    """The test the transcript reader exists for.

    YouTube's automatic captions repeat the tail of each cue and add a few
    words, because they are written to be read two lines at a time on screen.
    Concatenated naively this reads "so today we're making a so today we're
    making a carbonara..." -- three times the length and unusable.
    """
    text = transcripts.to_text(fixture("rolling.vtt"), "vtt")

    assert "so today we're making a carbonara" in text
    # The give-away for the bug: the opening phrase appearing more than once.
    assert text.count("so today we're") == 1
    assert text.count("carbonara and the first") == 1


def test_inline_timing_is_stripped():
    """Auto-captions carry per-word timestamps inside the cue text."""
    text = transcripts.to_text(fixture("rolling.vtt"), "vtt")

    assert "<" not in text
    assert "00:00:00" not in text


def test_entities_are_decoded():
    # Asserted on the characters rather than a phrase: reflow may put a line
    # break anywhere, and a test that also pins the wrap point fails for the
    # wrong reason.
    text = transcripts.to_text(fixture("rolling.vtt"), "vtt")

    assert "&amp;" not in text
    assert "&" in text


def test_the_words_all_survive():
    """Dedupe that is too eager is the other failure mode, and it loses the
    quantity you came for."""
    text = transcripts.to_text(fixture("rolling.vtt"), "vtt")

    assert "200 grams" in text
    assert "guanciale" in text


def test_srt_reads_the_same_way():
    text = transcripts.to_text(fixture("plain.srt"), "srt")

    assert "200 grams of guanciale" in text
    assert "Four egg yolks" in text
    # Cue numbers are not speech.
    assert not text.startswith("1")


def test_json3_skips_empty_events():
    """A json3 event with no `segs` is a timing marker, not silence to
    transcribe."""
    text = transcripts.to_text(fixture("captions.json3"), "json3")

    assert "200 grams of guanciale and four egg yolks" in text
    assert "None" not in text


def test_a_repeated_line_that_is_really_repeated_is_kept():
    """Only *consecutive* repeats are rolling captions. Someone saying the same
    thing twice a minute apart said it twice."""
    vtt = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\nstir it\n\n"
        "00:00:02.000 --> 00:00:03.000\nkeep going\n\n"
        "00:00:03.000 --> 00:00:04.000\nstir it\n"
    )

    assert transcripts.to_text(vtt, "vtt").count("stir it") == 2


def test_an_unknown_subtitle_format_is_refused_not_guessed():
    with pytest.raises(transcripts.TranscriptError):
        transcripts.to_text("whatever", "ttml")


def test_malformed_json3_is_refused():
    with pytest.raises(transcripts.TranscriptError):
        transcripts.to_text("not json at all", "json3")


def test_an_empty_file_is_empty_not_an_error():
    assert transcripts.to_text("WEBVTT\n\n", "vtt") == ""


def test_long_unpunctuated_speech_is_wrapped():
    """Auto-captions often have no punctuation at all, so the width wrap is the
    only thing keeping the result readable."""
    text = transcripts.reflow(" ".join(["word"] * 200))

    assert len(text.splitlines()) > 1
    assert all(len(line) <= 88 for line in text.splitlines())


# --------------------------------------------------------------------------
# which hosts are accepted
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc", SourceType.youtube),
        ("https://youtube.com/watch?v=abc", SourceType.youtube),
        ("https://m.youtube.com/watch?v=abc", SourceType.youtube),
        ("https://youtu.be/abc", SourceType.youtube),
        ("https://www.tiktok.com/@cook/video/123", SourceType.tiktok),
        ("https://www.instagram.com/reel/abc/", SourceType.instagram),
    ],
)
def test_known_hosts_are_recognised(url, expected):
    assert video_import.source_type_for(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/recipe",
        "https://vimeo.com/123",
        # The trap an endswith-without-the-dot check falls into.
        "https://notyoutube.com/watch?v=abc",
        "https://youtube.com.evil.test/watch?v=abc",
    ],
)
def test_other_hosts_are_not(url):
    assert video_import.source_type_for(url) is None


def test_an_unsupported_host_is_refused_with_a_way_forward(client):
    with pytest.raises(SourceFetchError) as exc:
        video_import.check_video_url("https://example.test/recipe")

    assert "normal link import" in str(exc.value)


def test_a_private_address_is_still_refused_on_a_known_host(monkeypatch):
    """The allowlist is not a substitute for the SSRF guard. A hostname on the
    list could still resolve somewhere private."""
    from app.services import web_import

    def boom(url):
        raise SourceFetchError("resolves to a private address")

    monkeypatch.setattr(video_import, "check_url", boom)

    with pytest.raises(SourceFetchError):
        video_import.check_video_url("https://www.youtube.com/watch?v=abc")


# --------------------------------------------------------------------------
# picking a subtitle track
# --------------------------------------------------------------------------


def track(ext, url="https://example.test/s"):
    return {"ext": ext, "url": url}


def test_written_captions_beat_automatic_ones():
    """Manual captions are what the uploader typed; automatic ones are a
    machine's guess at speech, and a guess about "two teaspoons" is exactly
    what the reviewer is checking."""
    info = {
        "subtitles": {"en": [track("vtt")]},
        "automatic_captions": {"en": [track("json3")]},
    }

    _, language, is_automatic = video_import.pick_subtitles(info)

    assert (language, is_automatic) == ("en", False)


def test_automatic_captions_are_used_when_there_are_no_others():
    info = {"automatic_captions": {"en": [track("vtt")]}}

    _, _, is_automatic = video_import.pick_subtitles(info)

    assert is_automatic is True


def test_json3_is_preferred_within_a_track():
    """It has no rolling repetition to undo, so it needs the least of the
    transcript reader."""
    info = {"subtitles": {"en": [track("srt"), track("json3"), track("vtt")]}}

    chosen, _, _ = video_import.pick_subtitles(info)

    assert chosen["ext"] == "json3"


def test_english_is_preferred_but_another_language_still_beats_nothing():
    info = {"subtitles": {"fr": [track("vtt")], "en-GB": [track("vtt")]}}
    _, language, _ = video_import.pick_subtitles(info)
    assert language == "en-GB"

    _, language, _ = video_import.pick_subtitles({"subtitles": {"fr": [track("vtt")]}})
    assert language == "fr"


def test_no_subtitles_at_all():
    assert video_import.pick_subtitles({})[0] is None


# --------------------------------------------------------------------------
# what gets structured, and what deliberately does not
# --------------------------------------------------------------------------

DESCRIPTION = """Proper Carbonara

Serves 2

200g guanciale
4 egg yolks
100g pecorino
400g spaghetti

Method:
Render the guanciale slowly.
Cook the spaghetti until just shy of done.
Toss off the heat with the eggs and cheese.
"""


def source(**overrides):
    defaults = dict(
        url="https://www.youtube.com/watch?v=abc",
        source_type=SourceType.youtube,
        title="THE ONLY CARBONARA RECIPE YOU NEED",
        uploader="Some Cook",
        description=DESCRIPTION,
        transcript="right so about 200 grams of guanciale and four yolks",
    )
    return video_import.VideoSource(**{**defaults, **overrides})


def test_the_description_is_what_gets_structured():
    result = video_import.payload_from_video(source())

    assert result.structured_from == "description"
    assert [i["name"] for i in result.payload["ingredients"]] == [
        "guanciale", "egg yolks", "pecorino", "spaghetti",
    ]
    assert len(result.payload["steps"]) == 3
    assert result.payload["servings"] == 2


def test_the_videos_own_title_wins():
    """It is what you will recognise in the queue. The parser's guess came from
    the description's first line, which is as often a channel tagline."""
    result = video_import.payload_from_video(source())

    assert result.payload["title"] == "THE ONLY CARBONARA RECIPE YOU NEED"


def test_the_source_is_recorded_on_the_payload():
    result = video_import.payload_from_video(source())

    assert result.payload["source_type"] == "youtube"
    assert result.payload["source_url"] == "https://www.youtube.com/watch?v=abc"


def test_speech_is_not_parsed_into_ingredients():
    """The decision this whole module turns on.

    Running the line heuristic over prose yields ingredients like "so today
    we're making a carbonara and the first thing you need is 200 grams of
    guanciale". That is worse than nothing, because it looks like data.
    """
    # Transcript text chosen because the line parser *does* bite on it --
    # reflowed captions wrap anywhere, so lines routinely start with a number.
    # Fed through, it yields the ingredient "guanciale and you want to render
    # that slowly". An earlier version of this test used prose the parser
    # happened to ignore, which meant it passed whether or not the guard
    # existed.
    speech = (
        "right so carbonara\n"
        "200 grams of guanciale and you want to render that slowly\n"
        "4 egg yolks in a bowl with the cheese"
    )

    result = video_import.payload_from_video(source(description="", transcript=speech))

    assert result.structured_from == "none"
    assert result.payload["ingredients"] == []
    assert result.payload["steps"] == []


def test_an_unstructurable_video_says_so_rather_than_failing():
    """An empty draft that admits it beats a refusal: the transcript is still
    worth having in the queue to work from."""
    result = video_import.payload_from_video(source(description=""))

    assert "doesn't try to structure speech" in result.note
    assert "Nothing could be structured automatically." in result.warnings


def test_a_description_with_no_method_is_flagged():
    """Ingredients without steps usually means the method is only spoken."""
    result = video_import.payload_from_video(
        source(description="Carbonara\n\n200g guanciale\n4 egg yolks\n")
    )

    assert result.structured_from == "description"
    assert any("only spoken" in w for w in result.warnings)


def test_automatic_captions_are_flagged_as_approximate():
    result = video_import.payload_from_video(source(transcript_is_automatic=True))

    assert any("approximate" in w for w in result.warnings)


def test_written_captions_are_not_flagged():
    result = video_import.payload_from_video(source(transcript_is_automatic=False))

    assert not any("approximate" in w for w in result.warnings)


def test_a_video_with_no_captions_says_so():
    result = video_import.payload_from_video(source(transcript=""))

    assert any("No captions" in w for w in result.warnings)


# --------------------------------------------------------------------------
# keeping both halves
# --------------------------------------------------------------------------


def test_both_halves_are_kept_and_labelled():
    """The spec's first listed pitfall is that captions alone miss a third to a
    half of a recipe, so both are stored -- and labelled, because "the
    description says 200g and the video says a big handful" is the
    disagreement worth seeing."""
    text = video_import.original_text(source(transcript_is_automatic=True))

    assert "--- description ---" in text
    assert "--- transcript (automatic captions) ---" in text
    assert "200g guanciale" in text
    assert "four yolks" in text


def test_a_missing_half_leaves_no_empty_heading():
    text = video_import.original_text(source(transcript=""))

    assert "transcript" not in text
    assert "--- description ---" in text


def test_the_caption_language_is_recorded():
    text = video_import.original_text(source(subtitle_language="fr"))

    assert "captions, fr" in text


# --------------------------------------------------------------------------
# the endpoint
# --------------------------------------------------------------------------


@pytest.fixture
def stub_video(monkeypatch):
    """Replace the one function that touches the network."""

    def install(video_source):
        monkeypatch.setattr(
            "app.routers.import_.video_import.fetch_video", lambda url: video_source
        )

    return install


def test_importing_a_video_creates_a_draft_not_a_recipe(client, stub_video):
    stub_video(source())

    response = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    )

    assert response.status_code == 201
    assert client.get("/recipes").json() == []
    assert len(client.get("/drafts").json()) == 1


def test_the_draft_records_that_it_came_from_a_video(client, stub_video):
    """`url_fetch` means a publisher typed the amounts into HTML. `video_fetch`
    means some of them were said out loud."""
    stub_video(source())

    draft = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    ).json()

    assert draft["provenance"]["import_method"] == "video_fetch"
    assert draft["provenance"]["source_type"] == "youtube"
    assert draft["provenance"]["source_title"] == "Some Cook"


def test_both_halves_reach_the_provenance(client, stub_video):
    stub_video(source())

    draft = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    ).json()

    assert "--- description ---" in draft["provenance"]["original_text"]
    assert "--- transcript" in draft["provenance"]["original_text"]


def test_the_warnings_reach_the_reviewer_as_the_drafts_note(client, stub_video):
    """Reusing the note the agent surface added: what the proposer was unsure
    about, addressed to whoever reviews it."""
    stub_video(source(description="", transcript_is_automatic=True))

    draft = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    ).json()

    assert "structure speech" in draft["note"]
    assert "approximate" in draft["note"]


def test_a_video_import_is_not_recorded_as_a_humans(client, stub_video):
    stub_video(source())

    draft = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    ).json()

    # It came through John's door, so a human asked for it -- the *content* is
    # machine-read, and that is what import_method says.
    assert draft["created_by"] == "human"
    assert draft["provenance"]["import_method"] == "video_fetch"


def test_a_title_can_be_given_instead_of_the_shouty_one(client, stub_video):
    stub_video(source())

    draft = client.post(
        "/import/video",
        json={"url": "https://www.youtube.com/watch?v=abc", "title": "Carbonara"},
    ).json()

    assert draft["title"] == "Carbonara"


def test_an_unsupported_host_is_a_400_not_a_500(client):
    response = client.post("/import/video", json={"url": "https://example.test/r"})

    assert response.status_code == 400
    assert "normal link import" in response.json()["detail"]


def test_a_dead_video_is_the_callers_problem(client, monkeypatch):
    def boom(url):
        raise SourceFetchError("Could not read that video: Private video")

    monkeypatch.setattr("app.routers.import_.video_import.fetch_video", boom)

    response = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=gone"}
    )

    assert response.status_code == 400
    assert "Private video" in response.json()["detail"]


def test_a_structured_video_draft_validates_and_promotes(client, stub_video):
    """End to end: the whole point is a draft you can actually approve."""
    stub_video(source())
    draft = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    ).json()

    assert client.post(f"/drafts/{draft['id']}/validate").json()["ok"] is True
    recipe = client.post(f"/drafts/{draft['id']}/promote").json()

    assert recipe["provenance"]["import_method"] == "video_fetch"
    assert [i["name"] for i in recipe["ingredients"]][0] == "guanciale"


def test_an_unstructured_video_draft_does_not_validate(client, stub_video):
    """And should not: it isn't a recipe yet. The transcript is there to make
    it one."""
    stub_video(source(description=""))
    draft = client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    ).json()

    assert client.post(f"/drafts/{draft['id']}/validate").json()["ok"] is False


def test_video_import_requires_auth(locked_client):
    response = locked_client.post(
        "/import/video", json={"url": "https://www.youtube.com/watch?v=abc"}
    )

    assert response.status_code == 401
