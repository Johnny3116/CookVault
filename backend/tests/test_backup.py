"""Export, restore, and proving the round trip.

A backup is worth exactly what a restore can prove. The test that matters is
`test_a_full_library_survives_a_round_trip`: build a library with something in
every table, export it, wipe everything, restore, and compare the *whole*
export byte for byte. Spot-checking a few fields is how a backup that quietly
drops a column passes its own tests for a year.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def full_library(client, recipe_payload, draft_payload):
    """A library with at least one row in every table the backup covers."""
    recipe = client.post("/recipes", json=recipe_payload).json()

    client.post("/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe["id"], "servings": 8})
    client.post("/shopping-list/generate", json={"recipe_ids": [recipe["id"]]})
    client.post("/shopping-list", json={"name": "bin bags"})
    client.post(
        f"/recipes/{recipe['id']}/cooked",
        json={"cooked_on": "2026-09-20", "rating": 4, "notes": "good"},
    )
    client.post("/pantry", json={"name": "olive oil", "note": "big tin"})
    client.post("/aisles/rules", json={"term": "gochujang", "aisle": "pantry"})
    # A draft plus its provenance, promoted so the provenance points at both.
    draft = client.post("/drafts", json=draft_payload).json()
    client.post(f"/drafts/{draft['id']}/promote")
    # And one left unpromoted, so both draft states are covered.
    client.post("/drafts", json={"title": "half an idea", "payload": {"title": ""}})
    return recipe


def wipe(client):
    for recipe in client.get("/recipes").json():
        client.delete(f"/recipes/{recipe['id']}")
    client.delete("/shopping-list")
    for item in client.get("/pantry").json():
        client.delete(f"/pantry/{item['id']}")
    for rule in client.get("/aisles/rules").json():
        client.delete(f"/aisles/rules/{rule['id']}")


# --------------------------------------------------------------------------
# the round trip
# --------------------------------------------------------------------------


def test_a_full_library_survives_a_round_trip(client, full_library):
    """The test the whole feature exists for.

    Compared in full rather than field by field: a backup that silently drops
    a column would pass a spot check and fail a restore.
    """
    before = client.get("/backup/export").json()

    wipe(client)
    assert client.get("/recipes").json() == []

    restored = client.post("/backup/restore", json={"confirm": "replace", "data": before})
    assert restored.status_code == 200

    after = client.get("/backup/export").json()
    assert after == before


def test_every_table_has_something_in_the_fixture(client, full_library):
    """Otherwise the round-trip test above proves less than it looks."""
    export = client.get("/backup/export").json()

    empty = [
        name for name, rows in export.items() if name != "format_version" and not rows
    ]
    assert empty == []


def test_ids_are_preserved(client, full_library):
    """A restore that renumbers looks right and compares unequal, and then a
    good backup is indistinguishable from a bad one."""
    before = client.get("/backup/export").json()
    recipe_id = before["recipes"][0]["id"]

    wipe(client)
    client.post("/backup/restore", json={"confirm": "replace", "data": before})

    assert client.get(f"/recipes/{recipe_id}").status_code == 200


def test_quantities_keep_their_precision(client, full_library):
    """Decimals are exported as strings, not floats: a third of a cup should
    survive a backup as the number it was."""
    export = client.get("/backup/export").json()

    quantities = [i["quantity"] for i in export["ingredients"] if i["quantity"] is not None]
    assert quantities
    assert all(isinstance(q, str) for q in quantities)


def test_derived_values_are_not_exported(client, full_library):
    """`times_cooked` comes back from the log and aisles from the rules.
    Exporting them would invite a restore that disagrees with its own data."""
    export = client.get("/backup/export").json()

    assert "times_cooked" not in export["recipes"][0]
    assert "last_cooked_on" not in export["recipes"][0]
    assert "aisle" not in export["shopping_list_items"][0]


def test_history_and_pantry_come_back(client, full_library):
    before = client.get("/backup/export").json()
    wipe(client)
    client.post("/backup/restore", json={"confirm": "replace", "data": before})

    assert len(client.get("/history").json()) == 1
    assert [i["name"] for i in client.get("/pantry").json()] == ["olive oil"]
    # By id: the library has more than one recipe, and which one sorts first
    # is not what this test is about.
    assert client.get(f"/recipes/{full_library['id']}").json()["times_cooked"] == 1


def test_a_promoted_draft_keeps_pointing_at_its_recipe(client, full_library):
    """The relationship most likely to break: provenance points at both a
    draft and the recipe it became."""
    before = client.get("/backup/export").json()
    wipe(client)
    client.post("/backup/restore", json={"confirm": "replace", "data": before})

    promoted = next(d for d in client.get("/drafts", params={"status_filter": "promoted"}).json())
    recipe = client.get(f"/recipes/{promoted['promoted_recipe_id']}").json()
    assert recipe["provenance"] is not None


# --------------------------------------------------------------------------
# refusing to do damage
# --------------------------------------------------------------------------


def test_restoring_needs_the_word_replace(client, full_library):
    """It replaces everything. An accidental restore cannot be undone from
    inside the app -- the thing it destroyed is what you would need."""
    export = client.get("/backup/export").json()

    response = client.post("/backup/restore", json={"confirm": "yes", "data": export})

    assert response.status_code == 400
    assert client.get("/recipes").json() != []


def test_an_unknown_format_version_is_refused(client, full_library):
    export = client.get("/backup/export").json()
    export["format_version"] = 99

    response = client.post("/backup/restore", json={"confirm": "replace", "data": export})

    assert response.status_code == 400
    assert "version" in response.json()["detail"]
    # And nothing was touched.
    assert client.get("/recipes").json() != []


def test_an_unrecognised_section_is_refused(client, full_library):
    export = client.get("/backup/export").json()
    export["something_else"] = [{"id": 1}]

    response = client.post("/backup/restore", json={"confirm": "replace", "data": export})

    assert response.status_code == 400
    assert client.get("/recipes").json() != []


def test_a_failed_restore_leaves_the_library_alone(client, full_library):
    """One transaction: a half-restored library is the worst outcome
    available."""
    before = client.get("/backup/export").json()
    broken = {**before, "ingredients": [{"id": "not-a-uuid", "recipe_id": None, "name": "x"}]}

    response = client.post("/backup/restore", json={"confirm": "replace", "data": broken})

    assert response.status_code >= 400
    after = client.get("/backup/export").json()
    assert after == before


def test_restoring_an_empty_library_is_allowed(client, full_library):
    """Starting over is a legitimate thing to want."""
    empty = {"format_version": 1}

    response = client.post("/backup/restore", json={"confirm": "replace", "data": empty})

    assert response.status_code == 200
    assert client.get("/recipes").json() == []


def test_backup_requires_auth(locked_client):
    assert locked_client.get("/backup/export").status_code == 401
    assert locked_client.post("/backup/restore", json={"confirm": "replace", "data": {}}).status_code == 401
