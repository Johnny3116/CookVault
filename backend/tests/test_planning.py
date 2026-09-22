"""Proposed weeks: suggesting them, editing them, approving them.

Two claims are worth more than the rest. The first is that suggestion is
arithmetic -- the same library and the same cook log produce the same week
twice, and every meal comes with the sentence that put it there. The second is
that nothing is planned until John says so, including when the proposal came
from CookVault itself.
"""

from __future__ import annotations

import pytest

from tests.test_agent_surface import AGENT_KEY, agent  # noqa: F401


@pytest.fixture
def week(client, recipe_payload):
    """Ten recipes, so a seven-day plan has room to not repeat."""
    return {
        name: client.post("/recipes", json={**recipe_payload, "title": name}).json()
        for name in [
            "Alpha", "Bravo", "Charlie", "Delta", "Echo",
            "Foxtrot", "Golf", "Hotel", "India", "Juliet",
        ]
    }


def planned_titles(client):
    by_id = {r["id"]: r["title"] for r in client.get("/recipes").json()}
    return [by_id[e["recipe_id"]] for e in client.get("/meal-plan").json()]


# --------------------------------------------------------------------------
# suggesting: arithmetic, not judgement
# --------------------------------------------------------------------------


def test_auto_fill_proposes_and_plans_nothing(client, week):
    """The whole shape of it. A proposal is not a plan."""
    response = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 7})

    assert response.status_code == 201
    assert len(response.json()["meals"]) == 7
    # The calendar is untouched until somebody approves it.
    assert client.get("/meal-plan").json() == []


def test_a_proposed_week_does_not_repeat_itself(client, week):
    meals = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 7}).json()["meals"]

    assert len({m["recipe_id"] for m in meals}) == 7


def test_every_meal_says_why_it_is_there(client, week):
    """A plan you cannot interrogate is one you override out of habit."""
    meals = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 3}).json()["meals"]

    assert all(m["reason"] for m in meals)
    assert all("never cooked" in m["reason"] for m in meals)


def test_the_same_library_proposes_the_same_week_twice(client, week):
    """Determinism is the point of doing this arithmetically. A suggester that
    answers differently each time is one nobody can debug."""
    first = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 5}).json()
    second = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 5}).json()

    assert [m["recipe_id"] for m in first["meals"]] == [m["recipe_id"] for m in second["meals"]]


def test_what_was_cooked_recently_is_pushed_back(client, week):
    """The cook log is what "diverse" is made of."""
    client.post(f"/recipes/{week['Alpha']['id']}/cooked", json={"cooked_on": "2026-10-04"})

    meals = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 3}).json()["meals"]

    assert week["Alpha"]["id"] not in {m["recipe_id"] for m in meals}


def test_something_cooked_long_ago_comes_back_around(client, week):
    client.post(f"/recipes/{week['Alpha']['id']}/cooked", json={"cooked_on": "2025-01-01"})

    meals = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 10}).json()["meals"]

    alpha = next(m for m in meals if m["recipe_id"] == week["Alpha"]["id"])
    assert "not cooked in" in alpha["reason"]


def test_what_is_already_planned_that_week_is_pushed_to_the_bottom(client, week):
    """A week should not serve the same thing twice. Pushed down rather than
    removed, because a caller with four recipes and seven days still needs an
    answer."""
    client.post(
        "/meal-plan",
        json={"date": "2026-10-07", "recipe_id": week["Alpha"]["id"], "mode": "manual"},
    )

    meals = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 5}).json()["meals"]

    assert week["Alpha"]["id"] not in {m["recipe_id"] for m in meals}


def test_a_favourite_wins_a_tie_but_does_not_take_over(client, week):
    """A nudge, not a thumb on the scale: it should not crowd out the variety
    this whole thing exists to produce."""
    client.patch(f"/recipes/{week['Juliet']['id']}", json={"is_favorite": True})

    meals = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 7}).json()["meals"]

    assert meals[0]["recipe_id"] == week["Juliet"]["id"]
    assert len({m["recipe_id"] for m in meals}) == 7


def test_a_favourite_cooked_yesterday_does_not_beat_something_never_cooked(client, week):
    """Where the size of the bonus is actually decided. A favourite should win
    a tie between equally stale recipes; it should not outvote the staleness
    this whole thing exists to measure, or "diverse" becomes "your favourites,
    repeatedly"."""
    client.patch(f"/recipes/{week['Alpha']['id']}", json={"is_favorite": True})
    client.post(f"/recipes/{week['Alpha']['id']}/cooked", json={"cooked_on": "2026-10-04"})

    meals = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 3}).json()["meals"]

    assert week["Alpha"]["id"] not in {m["recipe_id"] for m in meals}


def test_filters_narrow_what_can_be_proposed(client, week, recipe_payload):
    client.post("/recipes", json={**recipe_payload, "title": "All Day Braise", "cook_time": 300})

    meals = client.post(
        "/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 3, "max_total_time": 60}
    ).json()["meals"]

    by_id = {r["id"]: r["title"] for r in client.get("/recipes").json()}
    assert "All Day Braise" not in {by_id[m["recipe_id"]] for m in meals}


def test_fewer_recipes_than_days_is_said_out_loud(client, recipe_payload):
    """Rather than silently short. Whether to repeat something or leave a day
    empty is a decision, not a detail."""
    for name in ["One", "Two"]:
        client.post("/recipes", json={**recipe_payload, "title": name})

    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 7}).json()

    assert len(draft["meals"]) == 2
    assert "2 of 7 days" in draft["note"]


def test_an_empty_library_is_refused_rather_than_planned(client):
    response = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 7})

    assert response.status_code == 400
    assert "nothing to plan" in response.json()["detail"]


# --------------------------------------------------------------------------
# John approves
# --------------------------------------------------------------------------


def test_approving_creates_the_entries(client, week):
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 3}).json()

    response = client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    assert response.status_code == 200
    assert len(client.get("/meal-plan").json()) == 3


def test_approved_entries_are_recorded_as_auto(client, week):
    """The only place that mode is ever set. It records that the week was
    proposed, which is a different fact from what got cooked."""
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()

    client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    assert {e["mode"] for e in client.get("/meal-plan").json()} == {"auto"}


def test_approving_settles_the_draft(client, week):
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()

    client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    settled = client.get(f"/meal-plan/drafts/{draft['id']}").json()
    assert settled["status"] == "promoted"
    assert settled["approved_at"] is not None


def test_a_plan_cannot_be_approved_twice(client, week):
    """Otherwise a double-click plans the week twice."""
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()
    client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    assert client.post(f"/meal-plan/drafts/{draft['id']}/approve").status_code == 409
    assert len(client.get("/meal-plan").json()) == 2


def test_a_discarded_plan_cannot_be_approved(client, week):
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()
    client.post(f"/meal-plan/drafts/{draft['id']}/discard")

    assert client.post(f"/meal-plan/drafts/{draft['id']}/approve").status_code == 409
    assert client.get("/meal-plan").json() == []


def test_approving_checks_the_recipes_still_exist(client, week):
    """Resolved again at approval rather than trusted from when the plan was
    made. A recipe can be deleted in between, and planning a week around one
    that no longer exists is worse than saying so."""
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 7}).json()
    doomed = draft["meals"][0]["recipe_id"]
    client.delete(f"/recipes/{doomed}")

    response = client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    assert response.status_code == 422
    assert "no longer exist" in response.json()["detail"]


def test_a_failed_approval_plans_nothing_at_all(client, week):
    """No half-approved week: it is neither the plan nor the absence of one."""
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 7}).json()
    client.delete(f"/recipes/{draft['meals'][0]['recipe_id']}")

    client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    assert client.get("/meal-plan").json() == []
    assert client.get(f"/meal-plan/drafts/{draft['id']}").json()["status"] == "ready"


def test_a_plan_can_be_edited_before_approving(client, week):
    """Swapping Thursday's meal is the normal case. A plan that can only be
    taken whole or rejected whole is one that gets rejected."""
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()
    meals = draft["meals"]
    meals[0]["recipe_id"] = week["Juliet"]["id"]

    client.patch(f"/meal-plan/drafts/{draft['id']}", json={"meals": meals})
    client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    assert planned_titles(client)[0] == "Juliet"


def test_an_approved_plan_cannot_be_edited(client, week):
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()
    client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    assert client.patch(f"/meal-plan/drafts/{draft['id']}", json={"title": "again"}).status_code == 409


def test_deleting_an_approved_plan_leaves_the_week_alone(client, week):
    """The entries stand on their own once approved -- unlike a promoted recipe
    draft, there is no provenance to strip."""
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()
    client.post(f"/meal-plan/drafts/{draft['id']}/approve")

    client.delete(f"/meal-plan/drafts/{draft['id']}")

    assert len(client.get("/meal-plan").json()) == 2


def test_plans_are_listed_newest_first_and_filterable(client, week):
    first = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()
    client.post("/meal-plan/auto-fill", json={"start": "2026-11-02", "days": 2})
    client.post(f"/meal-plan/drafts/{first['id']}/discard")

    assert len(client.get("/meal-plan/drafts").json()) == 2
    discarded = client.get("/meal-plan/drafts", params={"status_filter": "discarded"}).json()
    assert [d["id"] for d in discarded] == [first["id"]]


def test_the_span_a_plan_covers_is_reported(client, week):
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 3}).json()

    assert draft["meals"][0]["date"] == "2026-10-05"
    assert draft["meals"][-1]["date"] == "2026-10-07"


# --------------------------------------------------------------------------
# the agent's side
# --------------------------------------------------------------------------


def test_suggest_returns_candidates_and_plans_nothing(agent, week):
    response = agent.post("/agent/suggest-meal-plan", json={"start": "2026-10-05", "days": 3})

    assert response.status_code == 200
    body = response.json()
    assert [d["date"] for d in body["days"]] == ["2026-10-05", "2026-10-06", "2026-10-07"]
    assert all(d["candidates"] for d in body["days"])
    assert agent.get("/meal-plan").json() == []
    assert agent.get("/meal-plan/drafts").json() == []


def test_candidates_are_dealt_so_the_top_pick_differs_each_day(agent, week):
    """Handing every day the same top five would make "candidates for seven
    days" a list of five, and a caller taking the first each day would cook the
    same thing all week."""
    body = agent.post("/agent/suggest-meal-plan", json={"start": "2026-10-05", "days": 5}).json()

    tops = [d["candidates"][0]["recipe"]["id"] for d in body["days"]]
    assert len(set(tops)) == 5


def test_every_candidate_carries_its_reason(agent, week):
    body = agent.post("/agent/suggest-meal-plan", json={"start": "2026-10-05", "days": 2}).json()

    assert all(c["reason"] for day in body["days"] for c in day["candidates"])


def test_suggest_says_when_there_are_fewer_recipes_than_days(agent, client, recipe_payload):
    client.post("/recipes", json={**recipe_payload, "title": "Only One"})

    body = agent.post("/agent/suggest-meal-plan", json={"start": "2026-10-05", "days": 7}).json()

    assert "repeat or stay empty" in body["note"]


def test_suggest_on_an_empty_library_is_empty_not_invented(agent):
    body = agent.post("/agent/suggest-meal-plan", json={"start": "2026-10-05", "days": 3}).json()

    assert all(d["candidates"] == [] for d in body["days"])
    assert "No recipes matched" in body["note"]


def test_the_agent_can_exclude_recipes(agent, week):
    body = agent.post(
        "/agent/suggest-meal-plan",
        json={"start": "2026-10-05", "days": 3, "exclude_recipe_ids": [week["Alpha"]["id"]]},
    ).json()

    offered = {c["recipe"]["id"] for day in body["days"] for c in day["candidates"]}
    assert week["Alpha"]["id"] not in offered


def test_the_agent_proposes_a_week_and_john_approves_it(agent, week):
    """The whole loop, end to end."""
    proposed = agent.post(
        "/agent/meal-plan-drafts",
        json={
            "title": "A balanced week",
            "meals": [
                {"date": "2026-10-05", "recipe_id": week["Alpha"]["id"], "reason": "light start"},
                {"date": "2026-10-06", "recipe_id": week["Bravo"]["id"]},
            ],
            "note": "Kept Monday light because the log says Sunday was a roast.",
            "agent_model": "qwen2.5:14b",
        },
    )

    assert proposed.status_code == 201
    # Proposed, not planned.
    assert agent.get("/meal-plan").json() == []

    agent.post(f"/meal-plan/drafts/{proposed.json()['id']}/approve")

    assert planned_titles(agent) == ["Alpha", "Bravo"]


def test_an_agent_plan_is_recorded_as_the_agents(agent, week):
    draft_id = agent.post(
        "/agent/meal-plan-drafts",
        json={"meals": [{"date": "2026-10-05", "recipe_id": week["Alpha"]["id"]}]},
    ).json()["id"]

    stored = agent.get(f"/meal-plan/drafts/{draft_id}").json()
    assert stored["created_by"] == "agent"
    assert stored["status"] == "ready"


def test_a_cookvault_proposal_is_not_recorded_as_the_agents(client, week):
    """Auto-fill involves no model at all, and should not claim one."""
    draft = client.post("/meal-plan/auto-fill", json={"start": "2026-10-05", "days": 2}).json()

    assert draft["created_by"] == "human"
    assert draft["agent_model"] is None


def test_the_agents_reasoning_reaches_the_reviewer(agent, week):
    draft_id = agent.post(
        "/agent/meal-plan-drafts",
        json={
            "meals": [{"date": "2026-10-05", "recipe_id": week["Alpha"]["id"], "reason": "quick"}],
            "note": "Short week, everything under 30 minutes.",
        },
    ).json()["id"]

    stored = agent.get(f"/meal-plan/drafts/{draft_id}").json()
    assert stored["note"] == "Short week, everything under 30 minutes."
    assert stored["meals"][0]["reason"] == "quick"


def test_a_plan_naming_a_recipe_that_does_not_exist_is_refused(agent, week):
    """Unlike a recipe draft, where being wrong is the point. A missing id is
    not a judgement call about content -- it is a reference that cannot
    resolve, and accepting it would queue a proposal that can never be
    approved."""
    response = agent.post(
        "/agent/meal-plan-drafts",
        json={"meals": [{"date": "2026-10-05", "recipe_id": "00000000-0000-0000-0000-000000000000"}]},
    )

    assert response.status_code == 422
    assert "No such recipe" in response.json()["detail"]


def test_an_empty_plan_is_refused(agent):
    assert agent.post("/agent/meal-plan-drafts", json={"meals": []}).status_code == 400


def test_the_agent_cannot_approve_its_own_plan(agent, week):
    """The same one-way door as recipe drafts."""
    draft_id = agent.post(
        "/agent/meal-plan-drafts",
        json={"meals": [{"date": "2026-10-05", "recipe_id": week["Alpha"]["id"]}]},
    ).json()["id"]

    assert agent.post(f"/agent/meal-plan-drafts/{draft_id}/approve").status_code == 404
    assert agent.get("/meal-plan").json() == []


def test_planning_requires_auth(locked_client):
    assert locked_client.post("/meal-plan/auto-fill", json={"start": "2026-10-05"}).status_code == 401
    assert locked_client.get("/meal-plan/drafts").status_code == 401
