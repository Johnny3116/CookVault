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


def test_an_entry_cannot_simply_be_labelled_auto(client, recipe_payload):
    """`auto` records that a week was proposed and approved, not chosen meal by
    meal. If anyone could set it, it would stop answering "where did this week
    come from?" -- so it is set in one place only, by approving a plan."""
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    refused = client.post(
        "/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id, "mode": "auto"}
    )

    assert refused.status_code == 400
    assert "auto-fill" in refused.json()["detail"]


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


def _names(items: list[dict]) -> list[str]:
    return sorted(item["name"] for item in items)


def _line(items: list[dict], name: str) -> dict:
    matches = [i for i in items if i["name"].lower() == name.lower()]
    assert len(matches) == 1, f"expected one {name!r} line, got {len(matches)}"
    return matches[0]


def _recipe(**overrides) -> dict:
    base = {
        "title": "R",
        "tags": [],
        "cook_methods": [],
        "ingredients": [],
        "steps": [],
        "alternates": [],
    }
    base.update(overrides)
    return base


def test_generate_merges_the_same_ingredient_across_recipes(client):
    """Two recipes each wanting a cup of stock is one line, not two."""
    first = client.post(
        "/recipes",
        json=_recipe(
            title="Soup",
            ingredients=[{"name": "stock", "quantity": 1, "unit": "cup", "category": "pantry_dry_good"}],
        ),
    ).json()["id"]
    second = client.post(
        "/recipes",
        json=_recipe(
            title="Risotto",
            ingredients=[{"name": "Stock", "quantity": 2, "unit": "cup", "category": "pantry_dry_good"}],
        ),
    ).json()["id"]

    items = client.post("/shopping-list/generate", json={"recipe_ids": [first, second]}).json()

    stock = _line(items, "stock")
    assert stock["quantity"] == "3.000"
    assert stock["unit"] == "cup"


def test_generate_converts_compatible_units_before_summing(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(
            ingredients=[
                {"name": "milk", "quantity": 1, "unit": "cup", "category": "raw_ingredient"},
                {"name": "milk", "quantity": 2, "unit": "tbsp", "category": "raw_ingredient"},
            ],
        ),
    ).json()["id"]

    items = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]}).json()

    milk = _line(items, "milk")
    assert milk["unit"] == "cup"
    assert float(milk["quantity"]) == 1.125


def test_generate_keeps_incompatible_units_as_separate_lines(client):
    """Adding 2 cloves to 1 tbsp would be inventing a number."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(
            ingredients=[
                {"name": "garlic", "quantity": 2, "unit": "cloves", "category": "raw_ingredient"},
                {"name": "garlic", "quantity": 1, "unit": "tbsp", "category": "raw_ingredient"},
            ],
        ),
    ).json()["id"]

    items = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]}).json()

    garlic = [i for i in items if i["name"] == "garlic"]
    assert len(garlic) == 2
    assert {i["unit"] for i in garlic} == {"cloves", "tbsp"}


def test_generate_does_not_merge_across_categories(client):
    """The same word in two columns stays in both, rather than picking one."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(
            ingredients=[
                {"name": "olive oil", "quantity": 1, "unit": "tbsp", "category": "pantry_dry_good"},
                {"name": "olive oil", "quantity": 1, "unit": "tbsp", "category": "spice_sauce"},
            ],
        ),
    ).json()["id"]

    items = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]}).json()

    assert {i["category"] for i in items if i["name"] == "olive oil"} == {
        "pantry_dry_good",
        "spice_sauce",
    }


def test_generating_twice_does_not_double_the_list(client):
    """The old behavior appended, so a second click silently doubled everything."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(
            ingredients=[{"name": "stock", "quantity": 1, "unit": "cup", "category": "pantry_dry_good"}],
        ),
    ).json()["id"]

    first = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]}).json()
    second = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]}).json()

    assert _names(first) == _names(second)
    assert _line(second, "stock")["quantity"] == "1.000"


def test_regenerating_preserves_hand_added_items(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "stock", "category": "pantry_dry_good"}]),
    ).json()["id"]
    client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]})
    client.post("/shopping-list", json={"name": "bin bags", "category": "misc"})

    items = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]}).json()

    assert "bin bags" in _names(items)
    assert _line(items, "bin bags")["is_generated"] is False
    assert _line(items, "stock")["is_generated"] is True


def test_generate_with_no_recipes_clears_the_generated_half(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "stock", "category": "pantry_dry_good"}]),
    ).json()["id"]
    client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]})
    client.post("/shopping-list", json={"name": "bin bags", "category": "misc"})

    items = client.post("/shopping-list/generate", json={"recipe_ids": []}).json()

    assert _names(items) == ["bin bags"]


def test_ingredients_without_amounts_do_not_gain_one(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(
            ingredients=[
                {"name": "salt", "category": "spice_sauce"},
                {"name": "salt", "category": "spice_sauce"},
            ],
        ),
    ).json()["id"]

    items = client.post("/shopping-list/generate", json={"recipe_ids": [recipe_id]}).json()

    assert _line(items, "salt")["quantity"] is None


def test_clear_checked_only_removes_ticked_items(client):
    keep = client.post("/shopping-list", json={"name": "keep", "category": "misc"}).json()["id"]
    drop = client.post("/shopping-list", json={"name": "drop", "category": "misc"}).json()["id"]
    client.patch(f"/shopping-list/{drop}", json={"is_checked": True})

    assert client.delete("/shopping-list?checked_only=true").status_code == 204

    assert [i["id"] for i in client.get("/shopping-list").json()] == [keep]


def test_clear_empties_the_whole_list(client):
    client.post("/shopping-list", json={"name": "keep", "category": "misc"})

    assert client.delete("/shopping-list").status_code == 204

    assert client.get("/shopping-list").json() == []
