"""What the agent may propose, and what it may not then do about it.

"AI proposes, CookVault validates, John approves" is only a slogan until each
clause has a test. The proposing is easy. The tests worth reading here are the
other two: an invalid proposal is accepted *and reported* rather than refused,
a promoted or discarded draft stops being editable, and a draft John wrote is
not something the agent can reach at all.
"""

from __future__ import annotations

import pytest

from tests.test_agent_surface import AGENT_KEY, agent, library  # noqa: F401


@pytest.fixture
def proposal(recipe_payload):
    return {
        "title": recipe_payload["title"],
        "payload": recipe_payload,
        "provenance": {
            "source_type": "youtube",
            "source_url": "https://example.test/watch?v=abc",
            "source_title": "Carbonara in 10 minutes",
            "original_text": "so you want about two zucchini, an apple, plenty of pepper",
            "agent_model": "qwen2.5:14b",
            "agent_version": "0.3.1",
        },
        "note": "The video says 'a splash' of oil; I guessed a tablespoon.",
    }


# --------------------------------------------------------------------------
# proposing
# --------------------------------------------------------------------------


def test_a_proposal_lands_in_the_review_queue_and_not_the_cookbook(agent, proposal):
    response = agent.post("/agent/recipe-drafts", json=proposal)

    assert response.status_code == 201
    assert response.json()["valid"] is True
    # The queue has it; the cookbook does not.
    assert len(agent.get("/drafts").json()) == 1
    assert agent.get("/recipes").json() == []


def test_a_proposal_is_recorded_as_the_agents(agent, proposal):
    """Who proposed it is the first thing worth knowing about a draft, so it
    is a fact on the row rather than something inferred from provenance."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    assert agent.get(f"/drafts/{draft_id}").json()["created_by"] == "agent"


def test_the_agent_cannot_claim_a_human_typed_it(agent, proposal):
    """The one field that says "a model touched this" is worthless if the
    model can set it to something else.

    Refused rather than ignored: silently dropping it is the failure mode where
    both sides think the call worked and only one of them is right."""
    proposal["provenance"]["import_method"] = "manual"

    response = agent.post("/agent/recipe-drafts", json=proposal)

    assert response.status_code == 422
    assert "import_method" in str(response.json()["detail"])


def test_whatever_the_agent_proposes_is_marked_as_the_agents(agent, proposal):
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    assert agent.get(f"/drafts/{draft_id}").json()["provenance"]["import_method"] == "agent"


def test_a_misspelled_field_is_named_rather_than_dropped(agent, proposal):
    """The same reasoning, generalised: an agent coded against a field that
    does not exist should be told, not left believing it took effect."""
    response = agent.post("/agent/recipe-drafts", json={**proposal, "notes": "typo for note"})

    assert response.status_code == 422
    assert "notes" in str(response.json()["detail"])


def test_the_model_that_proposed_it_is_recorded(agent, proposal):
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    provenance = agent.get(f"/drafts/{draft_id}").json()["provenance"]
    assert provenance["agent_model"] == "qwen2.5:14b"
    assert provenance["agent_version"] == "0.3.1"
    assert provenance["source_title"] == "Carbonara in 10 minutes"


def test_the_raw_source_is_kept_apart_from_the_structure(agent, proposal):
    """"Did the transcript say two teaspoons, or did the model decide that?" is
    the question worth asking about an imported recipe, and it is unanswerable
    once the two are merged."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    provenance = agent.get(f"/drafts/{draft_id}").json()["provenance"]
    assert provenance["original_text"].startswith("so you want about two zucchini")
    assert provenance["extracted_payload"]["title"] == "Test Carbonara"


def test_the_extracted_payload_survives_john_editing_the_draft(agent, proposal):
    """It is a frozen copy of the proposal, so "what did I change?" stays
    answerable after the review."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    agent.patch(f"/drafts/{draft_id}", json={"title": "Carbonara, fixed"})

    draft = agent.get(f"/drafts/{draft_id}").json()
    assert draft["title"] == "Carbonara, fixed"
    assert draft["provenance"]["extracted_payload"]["title"] == "Test Carbonara"


def test_the_note_reaches_the_reviewer(agent, proposal):
    """What the agent was unsure about is for John, and never becomes part of
    the recipe."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    assert "splash" in agent.get(f"/drafts/{draft_id}").json()["note"]


def test_a_note_does_not_end_up_in_the_promoted_recipe(agent, proposal):
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    recipe = agent.post(f"/drafts/{draft_id}/promote").json()

    assert "note" not in recipe


# --------------------------------------------------------------------------
# CookVault validates
# --------------------------------------------------------------------------


def test_an_invalid_proposal_is_accepted_and_reported(agent):
    """Not refused. A draft is allowed to be wrong -- that is the entire reason
    the queue exists -- and rejecting the proposals most worth reviewing would
    leave the agent guessing at what CookVault wanted."""
    response = agent.post("/agent/recipe-drafts", json={"payload": {"title": ""}})

    assert response.status_code == 201
    body = response.json()
    assert body["valid"] is False
    assert body["issues"]


def test_the_verdict_comes_back_with_the_write(agent, proposal):
    """Rather than needing a second call. The agent's next move depends on the
    answer, and a round trip it can skip is a round trip it will skip."""
    body = agent.post("/agent/recipe-drafts", json=proposal).json()

    assert body["valid"] is True
    assert body["status"] == "ready"


def test_a_proposal_that_does_not_validate_is_not_marked_ready(agent):
    body = agent.post("/agent/recipe-drafts", json={"payload": {"title": ""}}).json()

    assert body["status"] == "draft"


def test_warnings_do_not_block(agent, recipe_payload):
    """A warning is something to look at, not something to fix. Treating the
    two the same makes the severity meaningless."""
    payload = {
        **recipe_payload,
        "ingredients": [
            {"name": "zucchini", "quantity": 1, "unit": "ea", "category": "raw_ingredient"},
            {"name": "zucchini", "quantity": 2, "unit": "ea", "category": "raw_ingredient"},
        ],
    }

    body = agent.post("/agent/recipe-drafts", json={"payload": payload}).json()

    assert body["valid"] is True
    assert any(i["severity"] == "warning" for i in body["issues"])


def test_a_revision_is_revalidated(agent):
    """The verdict is about *this* payload. Carrying the old one forward would
    make the status a claim about something nobody checked."""
    draft_id = agent.post("/agent/recipe-drafts", json={"payload": {"title": ""}}).json()["id"]

    fixed = agent.patch(
        f"/agent/recipe-drafts/{draft_id}",
        json={
            "payload": {
                "title": "Now it has a title",
                "ingredients": [{"name": "beans", "category": "pantry_dry_good"}],
                "steps": [{"order": 1, "instruction_text": "Cook"}],
            }
        },
    ).json()

    assert fixed["valid"] is True
    assert fixed["status"] == "ready"


def test_a_revision_can_make_it_worse_and_says_so(agent, proposal):
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    worse = agent.patch(f"/agent/recipe-drafts/{draft_id}", json={"payload": {"title": ""}}).json()

    assert worse["valid"] is False
    assert worse["status"] == "draft"


# --------------------------------------------------------------------------
# John approves -- and the agent does not
# --------------------------------------------------------------------------


def test_the_agent_cannot_promote_its_own_proposal(agent, proposal):
    """The whole point. A ready draft is one CookVault is willing to promote,
    not one that promotes itself."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    assert agent.post(f"/agent/recipe-drafts/{draft_id}/promote").status_code == 404
    assert agent.get("/recipes").json() == []


def test_a_promoted_draft_can_no_longer_be_revised(agent, proposal):
    """Review is a one-way door. An agent that could reopen a decision would
    make the decision provisional."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]
    agent.post(f"/drafts/{draft_id}/promote")

    response = agent.patch(f"/agent/recipe-drafts/{draft_id}", json={"title": "second thoughts"})

    assert response.status_code == 409
    assert "promoted" in response.json()["detail"]


def test_a_discarded_draft_can_no_longer_be_revised(agent, proposal):
    """Saying no once should be enough."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]
    agent.post(f"/drafts/{draft_id}/discard")

    assert agent.patch(f"/agent/recipe-drafts/{draft_id}", json={"title": "again"}).status_code == 409


def test_promotion_carries_the_provenance_onto_the_recipe(agent, proposal):
    """So the cookbook entry keeps the record that a model wrote it."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    recipe = agent.post(f"/drafts/{draft_id}/promote").json()

    assert recipe["provenance"]["import_method"] == "agent"
    assert recipe["provenance"]["agent_model"] == "qwen2.5:14b"


# --------------------------------------------------------------------------
# other people's drafts
# --------------------------------------------------------------------------


def test_the_agent_cannot_read_a_draft_john_started(agent, draft_payload):
    """404, not 403: the two differ only in whether the answer confirms the row
    exists, and this surface has no reason to confirm anything about drafts it
    does not own."""
    mine = agent.post("/drafts", json=draft_payload).json()

    assert agent.get(f"/agent/recipe-drafts/{mine['id']}").status_code == 404


def test_the_agent_cannot_revise_a_draft_john_started(agent, draft_payload):
    """Even one whose provenance claims a model was involved -- authorship is
    which door the request came through, not what the content says about
    itself."""
    mine = agent.post("/drafts", json=draft_payload).json()
    assert mine["provenance"]["import_method"] == "agent"

    response = agent.patch(f"/agent/recipe-drafts/{mine['id']}", json={"title": "mine now"})

    assert response.status_code == 404
    assert agent.get(f"/drafts/{mine['id']}").json()["title"] == draft_payload["title"]


def test_the_agent_cannot_list_the_queue(agent, proposal, draft_payload):
    """What John is working on is not the agent's business, and there is no
    tool here that would tell it."""
    agent.post("/agent/recipe-drafts", json=proposal)
    agent.post("/drafts", json=draft_payload)

    assert agent.get("/agent/recipe-drafts").status_code == 405


def test_the_agent_can_read_back_its_own(agent, proposal):
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    body = agent.get(f"/agent/recipe-drafts/{draft_id}").json()

    assert body["id"] == draft_id
    assert body["valid"] is True


def test_a_missing_draft(agent):
    assert agent.get("/agent/recipe-drafts/00000000-0000-0000-0000-000000000000").status_code == 404


# --------------------------------------------------------------------------
# partial revision
# --------------------------------------------------------------------------


def test_revising_the_title_alone_leaves_the_payload(agent, proposal):
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    body = agent.patch(f"/agent/recipe-drafts/{draft_id}", json={"title": "Carbonara II"}).json()

    assert body["title"] == "Carbonara II"
    assert body["payload"]["ingredients"]


def test_a_note_can_be_cleared(agent, proposal):
    """A nullable field: "never mind, I worked it out" is a legitimate edit."""
    draft_id = agent.post("/agent/recipe-drafts", json=proposal).json()["id"]

    agent.patch(f"/agent/recipe-drafts/{draft_id}", json={"note": None})

    assert agent.get(f"/drafts/{draft_id}").json()["note"] is None


def test_drafts_created_by_hand_are_still_recorded_as_human(client, draft_payload):
    """The backfill claim, held up by the default: everything that does not
    come through the agent door is a human's."""
    draft = client.post("/drafts", json=draft_payload).json()

    assert draft["created_by"] == "human"
