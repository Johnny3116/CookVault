"""The vertical slice: recipe -> planned servings -> scaled shopping list."""

from __future__ import annotations


def _recipe(**overrides) -> dict:
    base = {
        "title": "R",
        "servings": 4,
        "tags": [],
        "cook_methods": [],
        "ingredients": [],
        "steps": [],
        "alternates": [],
    }
    base.update(overrides)
    return base


def _line(items: list[dict], name: str) -> dict:
    matches = [i for i in items if i["name"].lower() == name.lower()]
    assert len(matches) == 1, f"expected one {name!r} line, got {len(matches)}"
    return matches[0]


# --- scaled reads --------------------------------------------------------


def test_reading_a_recipe_unscaled_is_unchanged(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "rice", "quantity": 2, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]

    body = client.get(f"/recipes/{recipe_id}").json()

    assert body["servings"] == 4
    assert body["scaled_to_servings"] is None
    assert body["applied_scale"] is None
    assert body["ingredients"][0]["quantity"] == "2.000"


def test_reading_a_recipe_scaled_doubles_quantities(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "rice", "quantity": 2, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]

    body = client.get(f"/recipes/{recipe_id}?servings=8").json()

    assert body["scaled_to_servings"] == 8
    assert float(body["applied_scale"]) == 2.0
    assert float(body["ingredients"][0]["quantity"]) == 4.0
    assert body["servings"] == 8


def test_scaling_does_not_touch_the_stored_recipe(client):
    """Scaling is a read-time transform; the canonical recipe stays put."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "rice", "quantity": 2, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]

    client.get(f"/recipes/{recipe_id}?servings=8")
    stored = client.get(f"/recipes/{recipe_id}").json()

    assert stored["servings"] == 4
    assert float(stored["ingredients"][0]["quantity"]) == 2.0


def test_a_recipe_without_servings_comes_back_unscaled(client):
    """No recorded yield means no basis to scale from -- report that rather
    than scaling from a guess."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(servings=None,
                     ingredients=[{"name": "rice", "quantity": 2, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]

    body = client.get(f"/recipes/{recipe_id}?servings=8").json()

    assert body["applied_scale"] is None
    assert float(body["ingredients"][0]["quantity"]) == 2.0


def test_scaling_to_zero_or_negative_servings_is_refused(client):
    recipe_id = client.post("/recipes", json=_recipe()).json()["id"]

    assert client.get(f"/recipes/{recipe_id}?servings=0").status_code == 422
    assert client.get(f"/recipes/{recipe_id}?servings=-3").status_code == 422


def test_amountless_ingredients_survive_scaling(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "salt", "category": "spice_sauce"}]),
    ).json()["id"]

    body = client.get(f"/recipes/{recipe_id}?servings=8").json()

    assert body["ingredients"][0]["quantity"] is None


# --- meal plan carries planned servings ---------------------------------


def test_meal_plan_entries_record_servings_and_meal_type(client):
    recipe_id = client.post("/recipes", json=_recipe()).json()["id"]

    created = client.post(
        "/meal-plan",
        json={"date": "2026-09-23", "recipe_id": recipe_id, "mode": "manual",
              "meal_type": "dinner", "servings": 8},
    )

    assert created.status_code == 201, created.text
    assert created.json()["servings"] == 8
    assert created.json()["meal_type"] == "dinner"


def test_meal_plan_entries_can_be_edited(client):
    recipe_id = client.post("/recipes", json=_recipe()).json()["id"]
    entry_id = client.post(
        "/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id}
    ).json()["id"]

    patched = client.patch(f"/meal-plan/{entry_id}", json={"servings": 6, "date": "2026-09-24"})

    assert patched.status_code == 200, patched.text
    assert patched.json()["servings"] == 6
    assert patched.json()["date"] == "2026-09-24"


# --- the pipeline end to end --------------------------------------------


def test_generating_from_a_week_buys_the_servings_planned(client):
    """Planning risotto for 8 when it serves 4 must buy double."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "rice", "quantity": 2, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]
    client.post("/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id, "servings": 8})

    items = client.post(
        "/shopping-list/generate", json={"start": "2026-09-20", "end": "2026-09-26"}
    ).json()

    assert float(_line(items, "rice")["quantity"]) == 4.0


def test_generating_from_a_week_uses_the_recipe_as_written_when_no_servings_planned(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "rice", "quantity": 2, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]
    client.post("/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id})

    items = client.post(
        "/shopping-list/generate", json={"start": "2026-09-20", "end": "2026-09-26"}
    ).json()

    assert float(_line(items, "rice")["quantity"]) == 2.0


def test_the_week_window_excludes_entries_outside_it(client):
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "rice", "quantity": 2, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]
    client.post("/meal-plan", json={"date": "2026-10-05", "recipe_id": recipe_id})

    items = client.post(
        "/shopping-list/generate", json={"start": "2026-09-20", "end": "2026-09-26"}
    ).json()

    assert items == []


def test_scaled_entries_merge_with_each_other_across_the_week(client):
    """Two scaled plannings of the same recipe sum after scaling, not before."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[{"name": "rice", "quantity": 1, "unit": "cup",
                                   "category": "pantry_dry_good"}]),
    ).json()["id"]
    client.post("/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id, "servings": 8})
    client.post("/meal-plan", json={"date": "2026-09-24", "recipe_id": recipe_id, "servings": 2})

    items = client.post(
        "/shopping-list/generate", json={"start": "2026-09-20", "end": "2026-09-26"}
    ).json()

    # 1 cup x2 on Wednesday plus 1 cup x0.5 on Thursday.
    assert float(_line(items, "rice")["quantity"]) == 2.5


def test_scaling_happens_before_unit_conversion(client):
    """A scaled millilitre amount must convert and merge like any other."""
    recipe_id = client.post(
        "/recipes",
        json=_recipe(ingredients=[
            {"name": "stock", "quantity": 1, "unit": "cup", "category": "pantry_dry_good"},
            {"name": "stock", "quantity": 100, "unit": "ml", "category": "pantry_dry_good"},
        ]),
    ).json()["id"]
    client.post("/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe_id, "servings": 8})

    items = client.post(
        "/shopping-list/generate", json={"start": "2026-09-20", "end": "2026-09-26"}
    ).json()

    # (1 cup + 100 ml) doubled = 2 cup + 200 ml = 2.845 cup
    stock = _line(items, "stock")
    assert stock["unit"] == "cup"
    assert abs(float(stock["quantity"]) - 2.845) < 0.001


def test_week_and_ad_hoc_recipes_combine_in_one_generate(client):
    planned = client.post(
        "/recipes",
        json=_recipe(title="Planned", ingredients=[{"name": "rice", "quantity": 1, "unit": "cup",
                                                    "category": "pantry_dry_good"}]),
    ).json()["id"]
    extra = client.post(
        "/recipes",
        json=_recipe(title="Extra", ingredients=[{"name": "rice", "quantity": 1, "unit": "cup",
                                                  "category": "pantry_dry_good"}]),
    ).json()["id"]
    client.post("/meal-plan", json={"date": "2026-09-23", "recipe_id": planned, "servings": 8})

    items = client.post(
        "/shopping-list/generate",
        json={"start": "2026-09-20", "end": "2026-09-26", "recipe_ids": [extra]},
    ).json()

    # Planned doubled (2 cup) plus the ad-hoc one as written (1 cup).
    assert float(_line(items, "rice")["quantity"]) == 3.0


def test_start_and_end_must_be_given_together(client):
    assert client.post("/shopping-list/generate", json={"start": "2026-09-20"}).status_code == 422
    assert client.post("/shopping-list/generate", json={"end": "2026-09-26"}).status_code == 422


def test_start_after_end_is_refused(client):
    response = client.post(
        "/shopping-list/generate", json={"start": "2026-09-26", "end": "2026-09-20"}
    )
    assert response.status_code == 422
