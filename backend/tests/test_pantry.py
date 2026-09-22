"""The pantry, and the one thing it is allowed to do to a shopping list.

The tests that matter here are the ones pinning what it *doesn't* do. A pantry
that quietly removes lines is a pantry that sends you home without the cumin.
"""

from __future__ import annotations

import pytest


def test_a_pantry_item_is_a_name_and_a_note(client):
    item = client.post("/pantry", json={"name": "olive oil", "note": "the big tin"}).json()

    assert item["name"] == "olive oil"
    assert item["note"] == "the big tin"
    # No quantity, no expiry, deliberately.
    assert set(item) == {"id", "name", "note", "created_at", "updated_at"}


def test_duplicates_are_refused(client):
    client.post("/pantry", json={"name": "cumin"})

    assert client.post("/pantry", json={"name": "cumin"}).status_code == 409


def test_a_blank_name_is_refused(client):
    assert client.post("/pantry", json={"name": "  "}).status_code == 400


def test_items_come_back_alphabetically(client):
    for name in ["salt", "cumin", "olive oil"]:
        client.post("/pantry", json={"name": name})

    assert [i["name"] for i in client.get("/pantry").json()] == ["cumin", "olive oil", "salt"]


def test_renaming_and_removing(client):
    item = client.post("/pantry", json={"name": "cumin"}).json()

    renamed = client.patch(f"/pantry/{item['id']}", json={"name": "ground cumin"}).json()
    assert renamed["name"] == "ground cumin"

    assert client.delete(f"/pantry/{item['id']}").status_code == 204
    assert client.get("/pantry").json() == []


# --------------------------------------------------------------------------
# what it does to the shopping list
# --------------------------------------------------------------------------


def test_a_staple_is_flagged_not_removed(client):
    """The whole design in one test. Dropping the line would silently
    under-buy, which is worse than buying a second jar."""
    client.post("/pantry", json={"name": "olive oil"})
    client.post("/shopping-list", json={"name": "olive oil"})

    items = client.get("/shopping-list").json()

    assert len(items) == 1
    assert items[0]["in_pantry"] is True


def test_something_not_in_the_pantry_is_not_flagged(client):
    client.post("/pantry", json={"name": "olive oil"})
    client.post("/shopping-list", json={"name": "chicken thighs"})

    assert client.get("/shopping-list").json()[0]["in_pantry"] is False


def test_matching_is_the_same_notion_the_aisles_use(client):
    """One implementation, two callers: "olive oil" matches "extra virgin
    olive oil", and "ham" still does not match "hammer"."""
    client.post("/pantry", json={"name": "olive oil"})
    client.post("/pantry", json={"name": "ham"})
    client.post("/shopping-list", json={"name": "extra virgin olive oil"})
    client.post("/shopping-list", json={"name": "hammer"})

    flagged = {i["name"]: i["in_pantry"] for i in client.get("/shopping-list").json()}

    assert flagged["extra virgin olive oil"] is True
    assert flagged["hammer"] is False


def test_adding_to_the_pantry_flags_lines_that_already_existed(client):
    """Resolved per response, so it applies to the list you already have --
    the same reason aisles are not stored on the row."""
    client.post("/shopping-list", json={"name": "olive oil"})
    assert client.get("/shopping-list").json()[0]["in_pantry"] is False

    client.post("/pantry", json={"name": "olive oil"})

    assert client.get("/shopping-list").json()[0]["in_pantry"] is True


def test_generation_still_includes_staples(client, recipe_payload):
    """Generating a list from a recipe must not skip the pantry items. You
    still need to know the recipe wants them."""
    client.post("/pantry", json={"name": "zucchini"})
    recipe = client.post("/recipes", json=recipe_payload).json()

    items = client.post("/shopping-list/generate", json={"recipe_ids": [recipe["id"]]}).json()

    names = {i["name"] for i in items}
    assert "zucchini" in names
    assert next(i for i in items if i["name"] == "zucchini")["in_pantry"] is True


def test_emptying_the_pantry_unflags_everything(client):
    item = client.post("/pantry", json={"name": "olive oil"}).json()
    client.post("/shopping-list", json={"name": "olive oil"})

    client.delete(f"/pantry/{item['id']}")

    assert client.get("/shopping-list").json()[0]["in_pantry"] is False


def test_pantry_requires_auth(locked_client):
    assert locked_client.get("/pantry").status_code == 401
