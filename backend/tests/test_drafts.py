"""The draft lifecycle: create, edit, validate, promote.

These are the tests that have to hold before anything automated is allowed to
propose a recipe. The interesting ones are not the happy path -- they are the
refusals: a draft that shouldn't promote, a `ready` flag that shouldn't
survive an edit, and a gate that shouldn't trust that flag anyway.
"""

from __future__ import annotations

import copy

import pytest

from app.services.drafts import has_errors, validate_payload


def _errors(issues):
    return [i for i in issues if i.severity == "error"]


def _warnings(issues):
    return [i for i in issues if i.severity == "warning"]


# --------------------------------------------------------------------------
# validation: structure
# --------------------------------------------------------------------------


def test_valid_payload_has_no_issues(recipe_payload):
    assert validate_payload(recipe_payload) == []


def test_unparseable_payload_reports_the_field(recipe_payload):
    payload = copy.deepcopy(recipe_payload)
    payload["ingredients"][0]["quantity"] = "about two"

    issues = validate_payload(payload)

    assert has_errors(issues)
    # The whole point of per-field reporting: the message says which line.
    assert any("ingredients -> 0 -> quantity" in issue.field for issue in issues)


def test_structural_failure_stops_before_the_sense_layer(recipe_payload):
    """A payload that doesn't parse gets parse errors, not a pile of both.

    Complaining that a recipe has no steps, when `steps` didn't parse as a
    list in the first place, buries the message that matters.
    """
    payload = {"title": "Broken", "ingredients": "not a list", "steps": "also not a list"}

    issues = validate_payload(payload)

    assert has_errors(issues)
    assert all("ingredients" in i.field or "steps" in i.field for i in issues)
    assert not any("at least one step" in i.message for i in issues)


# --------------------------------------------------------------------------
# validation: sense
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda p: p.update(ingredients=[]), "at least one ingredient"),
        (lambda p: p.update(steps=[]), "at least one step"),
        (lambda p: p.update(title="   "), "needs a title"),
        (lambda p: p.update(servings=0), "greater than zero"),
        (lambda p: p.update(prep_time=-5), "cannot be negative"),
    ],
)
def test_useless_recipes_are_errors(recipe_payload, mutate, expected):
    payload = copy.deepcopy(recipe_payload)
    mutate(payload)

    issues = validate_payload(payload)

    assert has_errors(issues)
    assert any(expected in issue.message for issue in issues)


@pytest.mark.parametrize(
    "orders",
    [
        [1, 2, 2],  # repeated: the second silently wins in the UI
        [1, 3],  # gap: reads as a missing instruction
        [0, 1],  # zero-based: off by one against every display
        [2, 1],  # not sorted, but a valid set -- still fine
    ],
)
def test_step_numbering_must_be_a_real_sequence(recipe_payload, orders):
    payload = copy.deepcopy(recipe_payload)
    payload["steps"] = [{"order": o, "instruction_text": f"step {o}"} for o in orders]

    issues = validate_payload(payload)

    # [2, 1] is a complete 1..n set in the wrong order, which is fine: the
    # recipe sorts by order on read.
    expected_ok = sorted(orders) == list(range(1, len(orders) + 1))
    assert (not has_errors(issues)) == expected_ok


def test_unconvertible_unit_warns_but_does_not_block(recipe_payload):
    """"A handful of parsley" is a real thing to write.

    It will not merge in the shopping list, and on an extracted draft it is
    often invented -- so it is worth surfacing, and not worth refusing.
    """
    payload = copy.deepcopy(recipe_payload)
    payload["ingredients"][0]["unit"] = "handfuls"

    issues = validate_payload(payload)

    assert not has_errors(issues)
    assert any("handfuls" in issue.message for issue in _warnings(issues))


def test_written_units_that_do_resolve_are_not_flagged(recipe_payload):
    """The unit layer's aliases are what keeps this warning from crying wolf."""
    payload = copy.deepcopy(recipe_payload)
    payload["ingredients"][0]["unit"] = "Tablespoons"

    assert _warnings(validate_payload(payload)) == []


def test_duplicate_ingredient_warns(recipe_payload):
    payload = copy.deepcopy(recipe_payload)
    payload["ingredients"].append({"name": "Zucchini", "quantity": 1, "unit": "ea"})

    issues = validate_payload(payload)

    assert not has_errors(issues)
    assert any("zucchini" in issue.message for issue in _warnings(issues))


# --------------------------------------------------------------------------
# lifecycle
# --------------------------------------------------------------------------


def test_create_stores_payload_and_provenance(client, draft_payload):
    response = client.post("/drafts", json=draft_payload)
    assert response.status_code == 201

    body = response.json()
    assert body["status"] == "draft"
    assert body["payload"]["title"] == "Test Carbonara"

    prov = body["provenance"]
    assert prov["source_type"] == "youtube"
    assert prov["import_method"] == "agent"
    assert prov["agent_model"] == "some-extractor"
    # The raw text and the extracted structure are kept apart on purpose.
    assert "plenty of pepper" in prov["original_text"]
    assert prov["extracted_payload"]["title"] == "Test Carbonara"
    assert prov["recipe_id"] is None


def test_a_draft_may_be_stored_while_still_invalid(client):
    """Drafts are allowed to be wrong on arrival.

    Rejecting a bad payload at the door would mean the proposals most worth
    reviewing are the ones that can never be stored to review.
    """
    response = client.post("/drafts", json={"title": "Half an idea", "payload": {"title": ""}})

    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_validate_reports_and_records(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()

    result = client.post(f"/drafts/{draft['id']}/validate").json()

    assert result["ok"] is True
    assert result["issues"] == []
    assert client.get(f"/drafts/{draft['id']}").json()["status"] == "ready"


def test_validate_does_not_repair_the_payload(client, recipe_payload):
    """Validation reports; it never edits. Silently fixing a proposal would
    hide the very thing the reviewer is there to see."""
    broken = copy.deepcopy(recipe_payload)
    broken["steps"] = [{"order": 7, "instruction_text": "only step"}]
    draft = client.post("/drafts", json={"payload": broken}).json()

    result = client.post(f"/drafts/{draft['id']}/validate").json()

    assert result["ok"] is False
    after = client.get(f"/drafts/{draft['id']}").json()
    assert after["status"] == "draft"
    assert after["payload"]["steps"][0]["order"] == 7


def test_editing_the_payload_un_readies_the_draft(client, draft_payload):
    """`ready` is a claim about a specific payload.

    Letting it survive an edit would turn it into a claim about a payload
    nobody checked -- exactly what the status exists to prevent.
    """
    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/validate")
    assert client.get(f"/drafts/{draft['id']}").json()["status"] == "ready"

    changed = copy.deepcopy(draft_payload["payload"])
    changed["title"] = "Edited after approval"
    client.patch(f"/drafts/{draft['id']}", json={"payload": changed})

    assert client.get(f"/drafts/{draft['id']}").json()["status"] == "draft"


def test_renaming_a_draft_does_not_un_ready_it(client, draft_payload):
    """The title column is a label for the list; the payload is the recipe."""
    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/validate")

    client.patch(f"/drafts/{draft['id']}", json={"title": "Carbonara (from the video)"})

    after = client.get(f"/drafts/{draft['id']}").json()
    assert after["status"] == "ready"
    assert after["title"] == "Carbonara (from the video)"


# --------------------------------------------------------------------------
# promotion
# --------------------------------------------------------------------------


def test_promote_creates_the_recipe_with_its_children(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/validate")

    response = client.post(f"/drafts/{draft['id']}/promote")
    assert response.status_code == 201
    recipe = response.json()

    assert recipe["title"] == "Test Carbonara"
    assert [i["name"] for i in recipe["ingredients"]] == ["zucchini", "apple", "black pepper"]
    assert [s["order"] for s in recipe["steps"]] == [1, 2]
    assert len(recipe["alternates"]) == 1

    assert client.get("/recipes").json()[0]["id"] == recipe["id"]


def test_promotion_carries_provenance_onto_the_recipe(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/validate")

    recipe = client.post(f"/drafts/{draft['id']}/promote").json()

    prov = client.get(f"/recipes/{recipe['id']}").json()["provenance"]
    assert prov is not None
    assert prov["source_url"] == "https://example.test/watch?v=abc123"
    assert prov["agent_model"] == "some-extractor"
    # One row, now pointing at both -- not a copy that can drift.
    assert prov["id"] == draft_payload_provenance_id(client, draft["id"])


def draft_payload_provenance_id(client, draft_id: str) -> str:
    return client.get(f"/drafts/{draft_id}").json()["provenance"]["id"]


def test_promoted_draft_records_what_it_became(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()
    recipe = client.post(f"/drafts/{draft['id']}/promote").json()

    after = client.get(f"/drafts/{draft['id']}").json()
    assert after["status"] == "promoted"
    assert after["promoted_recipe_id"] == recipe["id"]
    assert after["promoted_at"] is not None


def test_promotion_refuses_an_invalid_draft(client, recipe_payload):
    broken = copy.deepcopy(recipe_payload)
    broken["ingredients"] = []
    draft = client.post("/drafts", json={"payload": broken}).json()

    response = client.post(f"/drafts/{draft['id']}/promote")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["ok"] is False
    assert any("at least one ingredient" in issue["message"] for issue in detail["issues"])
    # Nothing reached the cookbook.
    assert client.get("/recipes").json() == []
    assert client.get(f"/drafts/{draft['id']}").json()["status"] == "draft"


def test_promotion_revalidates_rather_than_trusting_the_ready_flag(client, draft_payload):
    """The gate re-runs validation instead of believing the stored status.

    A gate that trusts a cached answer is not a gate. This is the test that
    would catch someone "optimising" promote by checking `status == ready`.
    """
    from app.db import SessionLocal
    from app.models import DraftStatus, RecipeDraft

    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/validate")

    # Corrupt the payload behind the API's back, leaving `ready` in place --
    # what a direct database write, or a bug in some other path, would do.
    with SessionLocal() as session:
        row = session.get(RecipeDraft, draft["id"])
        row.payload = {"title": "Nothing but a title"}
        session.commit()
        assert row.status == DraftStatus.ready

    response = client.post(f"/drafts/{draft['id']}/promote")

    assert response.status_code == 422
    assert client.get("/recipes").json() == []


def test_a_promoted_draft_is_frozen(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/promote")

    assert client.patch(f"/drafts/{draft['id']}", json={"title": "again"}).status_code == 409
    assert client.post(f"/drafts/{draft['id']}/promote").status_code == 409
    assert client.post(f"/drafts/{draft['id']}/validate").status_code == 409
    assert client.post(f"/drafts/{draft['id']}/discard").status_code == 409


def test_promoting_twice_does_not_make_two_recipes(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/promote")
    client.post(f"/drafts/{draft['id']}/promote")

    assert len(client.get("/recipes").json()) == 1


def test_a_promoted_draft_cannot_be_deleted(client, draft_payload):
    """Deleting it would cascade away the recipe's provenance row."""
    draft = client.post("/drafts", json=draft_payload).json()
    recipe = client.post(f"/drafts/{draft['id']}/promote").json()

    assert client.delete(f"/drafts/{draft['id']}").status_code == 409
    assert client.get(f"/recipes/{recipe['id']}").json()["provenance"] is not None


# --------------------------------------------------------------------------
# discard and delete
# --------------------------------------------------------------------------


def test_discard_keeps_the_record_of_having_rejected_it(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()

    assert client.post(f"/drafts/{draft['id']}/discard").json()["status"] == "discarded"
    assert client.get(f"/drafts/{draft['id']}").status_code == 200
    assert client.post(f"/drafts/{draft['id']}/promote").status_code == 409


def test_delete_removes_a_draft_and_its_provenance(client, draft_payload):
    draft = client.post("/drafts", json=draft_payload).json()

    assert client.delete(f"/drafts/{draft['id']}").status_code == 204
    assert client.get(f"/drafts/{draft['id']}").status_code == 404


def test_list_filters_by_status(client, draft_payload):
    kept = client.post("/drafts", json=draft_payload).json()
    binned = client.post("/drafts", json={"title": "Nope", "payload": {}}).json()
    client.post(f"/drafts/{binned['id']}/discard")

    ids = [d["id"] for d in client.get("/drafts", params={"status_filter": "draft"}).json()]

    assert ids == [kept["id"]]


def test_missing_draft_is_404(client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/drafts/{missing}").status_code == 404
    assert client.post(f"/drafts/{missing}/promote").status_code == 404


def test_drafts_require_auth_when_the_gate_is_on(locked_client, draft_payload):
    assert locked_client.post("/drafts", json=draft_payload).status_code == 401
    assert locked_client.get("/drafts").status_code == 401
