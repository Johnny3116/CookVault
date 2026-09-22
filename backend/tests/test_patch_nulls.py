"""PATCH with an explicit null on a NOT NULL column.

Every field on a PATCH schema is optional, which is what makes a partial
update partial -- but `"title": null` is *set*, so it survives
`exclude_unset` and reaches the column as None. The database then raises
IntegrityError and FastAPI turns that into a 500: the app blaming itself for
what was really a bad request.

These endpoints should answer 422 and say which field, and the rows should be
left exactly as they were.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def recipe(client, recipe_payload):
    return client.post("/recipes", json=recipe_payload).json()


# --------------------------------------------------------------------------
# every PATCH surface, and every NOT NULL column it can reach
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["title", "source_type", "cook_methods", "tags", "is_favorite"]
)
def test_recipe_patch_rejects_null(client, recipe, field):
    response = client.patch(f"/recipes/{recipe['id']}", json={field: None})

    assert response.status_code == 422
    assert field in str(response.json())
    # and nothing changed
    assert client.get(f"/recipes/{recipe['id']}").json()["title"] == recipe["title"]


@pytest.mark.parametrize("field", ["name", "category", "position"])
def test_ingredient_patch_rejects_null(client, recipe, field):
    ingredient = recipe["ingredients"][0]

    response = client.patch(
        f"/recipes/{recipe['id']}/ingredients/{ingredient['id']}", json={field: None}
    )

    assert response.status_code == 422
    assert field in str(response.json())


@pytest.mark.parametrize("field", ["order", "instruction_text"])
def test_step_patch_rejects_null(client, recipe, field):
    step = recipe["steps"][0]

    response = client.patch(f"/recipes/{recipe['id']}/steps/{step['id']}", json={field: None})

    assert response.status_code == 422
    assert field in str(response.json())


@pytest.mark.parametrize("field", ["type", "original_value", "alternate_value"])
def test_alternate_patch_rejects_null(client, recipe, field):
    alternate = recipe["alternates"][0]

    response = client.patch(
        f"/recipes/{recipe['id']}/alternates/{alternate['id']}", json={field: None}
    )

    assert response.status_code == 422
    assert field in str(response.json())


@pytest.mark.parametrize("field", ["name", "category", "is_checked"])
def test_shopping_list_patch_rejects_null(client, field):
    item = client.post("/shopping-list", json={"name": "bin bags"}).json()

    response = client.patch(f"/shopping-list/{item['id']}", json={field: None})

    assert response.status_code == 422
    assert field in str(response.json())


def test_meal_plan_patch_rejects_null_date(client, recipe):
    entry = client.post(
        "/meal-plan", json={"date": "2026-09-23", "recipe_id": recipe["id"]}
    ).json()

    response = client.patch(f"/meal-plan/{entry['id']}", json={"date": None})

    assert response.status_code == 422
    assert "date" in str(response.json())


def test_draft_patch_rejects_null_payload(client):
    draft = client.post("/drafts", json={"title": "x", "payload": {"title": "x"}}).json()

    response = client.patch(f"/drafts/{draft['id']}", json={"payload": None})

    assert response.status_code == 422
    assert "payload" in str(response.json())


# --------------------------------------------------------------------------
# the fix must not break what PATCH is for
# --------------------------------------------------------------------------


def test_a_nullable_column_can_still_be_nulled(client, recipe):
    """This is the line the fix must not cross. `source_url` *is* nullable, so
    clearing it is a legitimate edit, not a mistake."""
    response = client.patch(f"/recipes/{recipe['id']}", json={"source_url": None})

    assert response.status_code == 200
    assert response.json()["source_url"] is None


def test_partial_updates_still_leave_other_fields_alone(client, recipe):
    response = client.patch(f"/recipes/{recipe['id']}", json={"prep_time": 12})

    assert response.status_code == 200
    body = response.json()
    assert body["prep_time"] == 12
    assert body["title"] == recipe["title"]
    assert body["tags"] == recipe["tags"]


def test_omitting_a_field_is_not_nulling_it(client, recipe):
    """The distinction the whole fix rests on: absent is not null."""
    response = client.patch(f"/recipes/{recipe['id']}", json={"servings": 8})

    assert response.status_code == 200
    assert response.json()["title"] == recipe["title"]


def test_several_nulls_are_reported_together(client, recipe):
    """One round trip should name every offending field, not just the first."""
    response = client.patch(f"/recipes/{recipe['id']}", json={"title": None, "tags": None})

    assert response.status_code == 422
    detail = str(response.json())
    assert "title" in detail and "tags" in detail
