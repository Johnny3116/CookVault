"""Recipe CRUD, with emphasis on the behaviors that were previously broken."""

from __future__ import annotations

import pytest
from sqlalchemy import text


def test_health_is_open(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_preserves_submitted_ingredient_order(client, recipe_payload):
    """Ingredients used to be ordered by their random UUID, which shuffled the
    four-column layout on every read."""
    created = client.post("/recipes", json=recipe_payload)
    assert created.status_code == 201, created.text
    body = created.json()

    assert [i["name"] for i in body["ingredients"]] == ["zucchini", "apple", "black pepper"]
    assert [i["position"] for i in body["ingredients"]] == [0, 1, 2]


def test_order_survives_a_round_trip(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    fetched = client.get(f"/recipes/{recipe_id}").json()

    assert [i["name"] for i in fetched["ingredients"]] == ["zucchini", "apple", "black pepper"]
    assert fetched["tags"] == ["italian", "weeknight"]
    # NUMERIC columns serialize as JSON strings, not numbers.
    assert float(fetched["estimated_cost"]) == 12.50


def test_patch_updates_scalars_without_disturbing_children(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    patched = client.patch(f"/recipes/{recipe_id}", json={"is_favorite": True})

    assert patched.status_code == 200
    assert patched.json()["is_favorite"] is True
    assert len(patched.json()["ingredients"]) == 3
    assert len(patched.json()["steps"]) == 2


def test_favorite_filter(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]
    client.patch(f"/recipes/{recipe_id}", json={"is_favorite": True})

    favorites = client.get("/recipes?favorite=true").json()
    others = client.get("/recipes?favorite=false").json()

    assert [r["id"] for r in favorites] == [recipe_id]
    assert others == []


def test_tag_filter(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    assert [r["id"] for r in client.get("/recipes?tag=italian").json()] == [recipe_id]
    assert client.get("/recipes?tag=thai").json() == []


def test_cook_method_filter(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    assert [r["id"] for r in client.get("/recipes?cook_method=stovetop").json()] == [recipe_id]
    assert client.get("/recipes?cook_method=air fryer").json() == []


def test_max_total_time_filter_sums_prep_and_cook(client, recipe_payload):
    quick = dict(recipe_payload, title="Quick", prep_time=5, cook_time=10)
    slow = dict(recipe_payload, title="Slow", prep_time=30, cook_time=60)
    client.post("/recipes", json=quick)
    client.post("/recipes", json=slow)

    assert [r["title"] for r in client.get("/recipes?max_total_time=20").json()] == ["Quick"]
    assert {r["title"] for r in client.get("/recipes?max_total_time=90").json()} == {"Quick", "Slow"}


def test_untimed_recipes_are_not_hidden_by_the_time_filter(client, recipe_payload):
    """An unknown time is not a long one; excluding these would hide most of a
    young library."""
    untimed = dict(recipe_payload, title="Untimed", prep_time=None, cook_time=None)
    client.post("/recipes", json=untimed)

    assert [r["title"] for r in client.get("/recipes?max_total_time=10").json()] == ["Untimed"]


def test_search_filter_matches_titles_case_insensitively(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    assert [r["id"] for r in client.get("/recipes?search=carbonara").json()] == [recipe_id]
    assert client.get("/recipes?search=lasagne").json() == []


def test_filters_combine(client, recipe_payload):
    client.post("/recipes", json=dict(recipe_payload, title="Fast Italian", prep_time=5, cook_time=5))
    client.post("/recipes", json=dict(recipe_payload, title="Slow Italian", prep_time=60, cook_time=60))

    matched = client.get("/recipes?tag=italian&max_total_time=15").json()

    assert [r["title"] for r in matched] == ["Fast Italian"]


def test_facets_report_values_actually_in_use(client, recipe_payload):
    client.post("/recipes", json=recipe_payload)
    client.post("/recipes", json=dict(recipe_payload, tags=["thai"], cook_methods=["wok"]))

    facets = client.get("/recipes/facets").json()

    assert facets["tags"] == ["italian", "thai", "weeknight"]
    assert facets["cook_methods"] == ["stovetop", "wok"]


def test_facets_route_is_not_shadowed_by_the_recipe_id_route(client):
    """/recipes/facets must be declared before /recipes/{recipe_id}, or FastAPI
    tries to parse "facets" as a UUID."""
    response = client.get("/recipes/facets")

    assert response.status_code == 200
    assert response.json() == {"tags": [], "cook_methods": []}


def test_put_replaces_recipe_and_children(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    replacement = dict(recipe_payload)
    replacement["title"] = "Edited Carbonara"
    replacement["ingredients"] = [
        {"name": "black pepper", "category": "spice_sauce"},
        {"name": "guanciale", "quantity": 100, "unit": "g", "category": "raw_ingredient"},
    ]
    replacement["steps"] = [{"order": 1, "instruction_text": "Only one step now"}]
    replacement["alternates"] = []
    replaced = client.put(f"/recipes/{recipe_id}", json=replacement)

    assert replaced.status_code == 200, replaced.text
    body = replaced.json()
    assert body["title"] == "Edited Carbonara"
    assert [i["name"] for i in body["ingredients"]] == ["black pepper", "guanciale"]
    assert [i["position"] for i in body["ingredients"]] == [0, 1]
    assert len(body["steps"]) == 1
    assert body["alternates"] == []


def test_put_leaves_no_orphaned_child_rows(client, recipe_payload):
    from app.db import engine

    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]
    replacement = dict(recipe_payload)
    replacement["ingredients"] = [{"name": "guanciale", "category": "raw_ingredient"}]
    replacement["steps"] = [{"order": 1, "instruction_text": "Only one step now"}]
    replacement["alternates"] = []
    client.put(f"/recipes/{recipe_id}", json=replacement)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ingredients")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM steps")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM alternates")).scalar() == 0


def test_put_on_missing_recipe_is_404(client, recipe_payload):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.put(f"/recipes/{missing}", json=recipe_payload).status_code == 404


def test_adding_one_ingredient_appends_to_the_end(client, recipe_payload):
    """A single add must not collide with position 0."""
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    added = client.post(
        f"/recipes/{recipe_id}/ingredients",
        json={"name": "egg", "category": "raw_ingredient"},
    )

    assert added.status_code == 201, added.text
    assert added.json()["position"] == 3
    listed = client.get(f"/recipes/{recipe_id}/ingredients").json()
    assert [i["name"] for i in listed] == ["zucchini", "apple", "black pepper", "egg"]


def test_ingredient_patch_is_genuinely_partial(client, recipe_payload):
    """The PATCH schemas used to have required fields, so a partial update was
    impossible -- a PUT wearing a PATCH's name.

    This deliberately omits `name`, which the old schema required: sending it
    would pass against either schema and prove nothing.
    """
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]
    ingredient_id = client.get(f"/recipes/{recipe_id}/ingredients").json()[2]["id"]

    patched = client.patch(
        f"/recipes/{recipe_id}/ingredients/{ingredient_id}",
        json={"unit": "tsp"},
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["unit"] == "tsp"
    assert patched.json()["name"] == "black pepper"
    assert patched.json()["category"] == "spice_sauce"


def test_step_patch_is_genuinely_partial(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]
    step_id = client.get(f"/recipes/{recipe_id}/steps").json()[0]["id"]

    patched = client.patch(f"/recipes/{recipe_id}/steps/{step_id}", json={"notes": "watch it"})

    assert patched.status_code == 200, patched.text
    assert patched.json()["notes"] == "watch it"
    assert patched.json()["instruction_text"] == "Boil water"


def test_alternate_patch_is_genuinely_partial(client, recipe_payload):
    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]
    alternate_id = client.get(f"/recipes/{recipe_id}/alternates").json()[0]["id"]

    patched = client.patch(
        f"/recipes/{recipe_id}/alternates/{alternate_id}", json={"notes": "works fine"}
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["notes"] == "works fine"
    assert patched.json()["original_value"] == "zucchini"


def test_child_routes_reject_an_id_from_another_recipe(client, recipe_payload):
    first = client.post("/recipes", json=recipe_payload).json()["id"]
    second = client.post("/recipes", json=recipe_payload).json()["id"]
    ingredient_of_first = client.get(f"/recipes/{first}/ingredients").json()[0]["id"]

    mismatched = client.patch(
        f"/recipes/{second}/ingredients/{ingredient_of_first}", json={"name": "nope"}
    )

    assert mismatched.status_code == 404


def test_delete_cascades_to_children(client, recipe_payload):
    from app.db import engine

    recipe_id = client.post("/recipes", json=recipe_payload).json()["id"]

    assert client.delete(f"/recipes/{recipe_id}").status_code == 204
    assert client.get(f"/recipes/{recipe_id}").status_code == 404
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ingredients")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM steps")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM alternates")).scalar() == 0


def test_nothing_is_left_faking_a_result(client):
    """What is unbuilt should say so rather than return something plausible.

    This test has outlived both of its subjects. `/import` was the first to go
    -- see tests/test_import.py. Auto-fill was the second: it proposes a week
    from the cook log now (tests/test_planning.py) instead of answering 501.
    What is left unbuilt is the *outbound* Agent Zero client, which is a module
    rather than an endpoint and raises rather than guessing -- so the assertion
    here is that nothing is quietly pretending.
    """
    from app import agent_zero_client

    # Not configured -> AgentZeroNotConfigured; configured -> NotImplementedError.
    # Either way it refuses rather than returning something made up.
    with pytest.raises((agent_zero_client.AgentZeroNotConfigured, NotImplementedError)):
        agent_zero_client.structure_recipe_text("some text")
