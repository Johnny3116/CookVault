"""Shopping lists and manual meal planning."""

from __future__ import annotations


def test_generate_copies_every_ingredient_of_the_recipe(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    generated = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]})

    assert generated.status_code == 200, generated.text
    assert {item["name"] for item in generated.json()} == {"zucchini", "apple", "black pepper"}
    assert {item["category"] for item in generated.json()} == {"raw_ingredient", "spice_sauce"}


def test_generate_rejects_an_unknown_recipe(client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post("/shopping-list/generate", json={"recipe_ids": [missing]}).status_code == 404


def test_items_can_be_added_checked_off_and_removed(client):
    added = client.post("/shopping-list", json={"name": "paper towels", "category": "misc"})
    assert added.status_code == 201, added.text
    item_id = added.json()["id"]
    assert added.json()["is_checked"] is False

    checked = client.patch(f"/shopping-list/{item_id}", json={"is_checked": True})
    assert checked.json()["is_checked"] is True
    assert checked.json()["name"] == "paper towels"

    assert client.delete(f"/shopping-list/{item_id}").status_code == 204
    assert client.get("/shopping-list").json() == []


def test_manual_meal_plan_entries_round_trip(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    created = client.post(
        "/meal-plan",
        json={"date": "2026-09-23", "recipe_id": recipe_id, "mode": "manual"},
    )

    assert created.status_code == 201, created.text
    listed = client.get("/meal-plan?start=2026-09-20&end=2026-09-26").json()
    assert [e["id"] for e in listed] == [created.json()["id"]]
    # Outside the requested window.
    assert client.get("/meal-plan?start=2026-10-01&end=2026-10-07").json() == []


def test_auto_mode_entries_are_refused_until_phase_two(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    refused = client.post(
        "/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id, "mode": "auto"}
    )

    assert refused.status_code == 501


def test_deleting_a_recipe_removes_its_meal_plan_entries(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]
    client.post("/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id, "mode": "manual"})

    client.delete(f"/recipes/{recipe_id}")

    assert client.get("/meal-plan").json() == []


def test_finder_matches_saved_recipes_by_title(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    found = client.post("/finder/search", json={"query": "Carbonara"})

    assert found.status_code == 200
    assert [r["id"] for r in found.json()["from_collection"]] == [recipe_id]
    # Web search is Phase 2 and says so rather than returning nothing silently.
    assert found.json()["new_finds"] == []
    assert "Phase 2" in found.json()["new_finds_note"]
