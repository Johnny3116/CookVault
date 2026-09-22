"""The cooking log, and the two facts derived from it.

The derived counters are the interesting part: `times_cooked` and
`last_cooked_on` are computed from the log rather than incremented on the
recipe, so the tests worth having are the ones that would catch a counter
drifting away from the thing it counts.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

TODAY = date.today()


@pytest.fixture
def recipe(client, recipe_payload):
    return client.post("/recipes", json=recipe_payload).json()


def log(client, recipe_id, **kwargs):
    return client.post(f"/recipes/{recipe_id}/cooked", json=kwargs).json()


# --------------------------------------------------------------------------
# logging
# --------------------------------------------------------------------------


def test_logging_defaults_to_today(client, recipe):
    """Logging a meal you have just eaten is the common case."""
    entry = log(client, recipe["id"])

    assert entry["cooked_on"] == TODAY.isoformat()
    assert entry["rating"] is None


def test_logging_keeps_what_you_actually_made(client, recipe):
    entry = log(
        client,
        recipe["id"],
        cooked_on="2026-09-20",
        servings_made=6,
        rating=4,
        notes="needed longer than it said",
    )

    assert entry["servings_made"] == 6
    assert entry["rating"] == 4
    assert "longer" in entry["notes"]


def test_the_same_recipe_can_be_logged_twice_in_a_day(client, recipe):
    """People do cook the same thing for lunch and dinner. Refusing that
    would make the log lie to keep a constraint happy."""
    log(client, recipe["id"], cooked_on="2026-09-20")
    log(client, recipe["id"], cooked_on="2026-09-20")

    assert len(client.get(f"/recipes/{recipe['id']}/history").json()) == 2


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_a_rating_outside_one_to_five_is_refused(client, recipe, rating):
    assert client.post(f"/recipes/{recipe['id']}/cooked", json={"rating": rating}).status_code == 422


def test_servings_made_must_be_positive(client, recipe):
    response = client.post(f"/recipes/{recipe['id']}/cooked", json={"servings_made": 0})

    # A bad request, answered as one. The check constraint stays as a
    # backstop so a stray write cannot leave nonsense in the data either.
    assert response.status_code == 422


def test_logging_against_a_missing_recipe_is_404(client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/recipes/{missing}/cooked", json={}).status_code == 404


# --------------------------------------------------------------------------
# the derived facts
# --------------------------------------------------------------------------


def test_a_recipe_starts_uncooked(client, recipe):
    fresh = client.get(f"/recipes/{recipe['id']}").json()

    assert fresh["times_cooked"] == 0
    assert fresh["last_cooked_on"] is None


def test_counters_follow_the_log(client, recipe):
    log(client, recipe["id"], cooked_on="2026-09-01")
    log(client, recipe["id"], cooked_on="2026-09-20")
    log(client, recipe["id"], cooked_on="2026-09-10")

    body = client.get(f"/recipes/{recipe['id']}").json()

    assert body["times_cooked"] == 3
    # The most recent, not the most recently *added*.
    assert body["last_cooked_on"] == "2026-09-20"


def test_deleting_a_log_entry_moves_the_counters_back(client, recipe):
    """The case a stored counter gets wrong. Derived values cannot drift."""
    log(client, recipe["id"], cooked_on="2026-09-01")
    latest = log(client, recipe["id"], cooked_on="2026-09-20")

    client.delete(f"/history/{latest['id']}")

    body = client.get(f"/recipes/{recipe['id']}").json()
    assert body["times_cooked"] == 1
    assert body["last_cooked_on"] == "2026-09-01"


def test_editing_a_date_moves_last_cooked(client, recipe):
    entry = log(client, recipe["id"], cooked_on="2026-09-01")

    client.patch(f"/history/{entry['id']}", json={"cooked_on": "2026-09-25"})

    assert client.get(f"/recipes/{recipe['id']}").json()["last_cooked_on"] == "2026-09-25"


def test_counters_appear_in_the_library_listing(client, recipe):
    log(client, recipe["id"], cooked_on="2026-09-20")

    listed = client.get("/recipes").json()[0]

    assert listed["times_cooked"] == 1
    assert listed["last_cooked_on"] == "2026-09-20"


def test_deleting_a_recipe_takes_its_history(client, recipe):
    log(client, recipe["id"])

    client.delete(f"/recipes/{recipe['id']}")

    assert client.get("/history").json() == []


# --------------------------------------------------------------------------
# the feed and the sorts
# --------------------------------------------------------------------------


def test_recent_history_carries_titles(client, recipe):
    """Otherwise reading the feed means a lookup per row."""
    log(client, recipe["id"], cooked_on="2026-09-20")

    feed = client.get("/history").json()

    assert feed[0]["recipe_title"] == recipe["title"]


def test_recent_history_is_newest_first(client, recipe_payload):
    first = client.post("/recipes", json={**recipe_payload, "title": "One"}).json()
    second = client.post("/recipes", json={**recipe_payload, "title": "Two"}).json()
    log(client, first["id"], cooked_on="2026-09-01")
    log(client, second["id"], cooked_on="2026-09-20")

    assert [e["recipe_title"] for e in client.get("/history").json()] == ["Two", "One"]


def test_history_can_be_narrowed_to_recent_days(client, recipe):
    log(client, recipe["id"], cooked_on=(TODAY - timedelta(days=90)).isoformat())
    log(client, recipe["id"], cooked_on=TODAY.isoformat())

    recent = client.get("/history", params={"since": (TODAY - timedelta(days=30)).isoformat()})

    assert len(recent.json()) == 1


def test_sort_by_last_cooked_puts_the_neglected_first(client, recipe_payload):
    """The question this is for: what have I not made in ages."""
    never = client.post("/recipes", json={**recipe_payload, "title": "Never made"}).json()
    ages = client.post("/recipes", json={**recipe_payload, "title": "Ages ago"}).json()
    lately = client.post("/recipes", json={**recipe_payload, "title": "Last week"}).json()
    log(client, ages["id"], cooked_on="2026-01-05")
    log(client, lately["id"], cooked_on=TODAY.isoformat())

    titles = [r["title"] for r in client.get("/recipes", params={"sort": "last_cooked"}).json()]

    # Never is the extreme case of "a long time ago", not a missing answer.
    assert titles == ["Never made", "Ages ago", "Last week"]
    assert never["id"]


def test_sort_by_most_cooked(client, recipe_payload):
    once = client.post("/recipes", json={**recipe_payload, "title": "Once"}).json()
    thrice = client.post("/recipes", json={**recipe_payload, "title": "Thrice"}).json()
    log(client, once["id"])
    for _ in range(3):
        log(client, thrice["id"])

    titles = [r["title"] for r in client.get("/recipes", params={"sort": "most_cooked"}).json()]

    assert titles[:2] == ["Thrice", "Once"]


def test_an_unknown_sort_falls_back_rather_than_failing(client, recipe):
    """A typo in a query string should not take the library down."""
    assert client.get("/recipes", params={"sort": "nonsense"}).status_code == 200


def test_history_requires_auth(locked_client):
    assert locked_client.get("/history").status_code == 401
