"""The gate, and the shape of what is behind it.

The tests that matter most here are the negative ones. A tool surface is
defined by what it cannot do, and "the agent can't promote a draft" is only
true for as long as nobody mounts a convenient extra route. So the surface is
pinned as a literal list: adding an endpoint to the agent router fails this
file until someone writes down what it is and why the agent may have it.
"""

from __future__ import annotations

import pytest

AGENT_KEY = "test-agent-key-long-enough-to-be-accepted"


@pytest.fixture
def agent(client):
    """A client carrying the agent key. `client` already disabled the password
    gate, which is the point: the two credentials are unrelated."""
    from app.config import settings

    settings.agent_api_key = AGENT_KEY
    client.headers.update({"X-API-Key": AGENT_KEY})
    yield client
    settings.agent_api_key = None


@pytest.fixture
def agent_off(client):
    from app.config import settings

    settings.agent_api_key = None
    return client


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------


def test_the_surface_is_off_until_a_key_is_configured(agent_off):
    """Not 401 but 503: "nobody turned this on" and "you got the key wrong"
    are different problems and lead to different fixes."""
    response = agent_off.get("/agent/manifest")

    assert response.status_code == 503
    assert "AGENT_API_KEY" in response.json()["detail"]


def test_a_missing_key_is_refused(agent):
    del agent.headers["X-API-Key"]

    assert agent.get("/agent/manifest").status_code == 401


def test_a_wrong_key_is_refused(agent):
    agent.headers.update({"X-API-Key": "not-the-key-but-also-long-enough-ok"})

    assert agent.get("/agent/manifest").status_code == 401


def test_a_short_key_is_refused_at_startup():
    """A weak key fails to boot rather than failing mysteriously later. This is
    the only credential in front of a surface that can write."""
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(agent_api_key="short")


def test_johns_password_does_not_open_the_agent_surface(locked_client):
    """The two doors are separate. A session cookie is not an agent key, so a
    mistake in the web UI cannot reach tools the UI has no business calling."""
    from app.config import settings
    from tests.conftest import TEST_PASSWORD

    settings.agent_api_key = AGENT_KEY
    try:
        locked_client.post("/auth/login", json={"password": TEST_PASSWORD})
        # The cookie works on John's surface...
        assert locked_client.get("/recipes").status_code == 200
        # ...and buys nothing here.
        assert locked_client.get("/agent/manifest").status_code == 401
    finally:
        settings.agent_api_key = None


def test_the_agent_key_does_not_open_johns_surface(locked_client):
    """And the other way round: a leaked agent key is not a way to promote a
    draft or restore a backup."""
    from app.config import settings

    settings.agent_api_key = AGENT_KEY
    locked_client.headers.update({"X-API-Key": AGENT_KEY})
    try:
        assert locked_client.get("/recipes").status_code == 401
        assert locked_client.get("/backup/export").status_code == 401
    finally:
        settings.agent_api_key = None


# --------------------------------------------------------------------------
# the surface itself
# --------------------------------------------------------------------------

# Every route the agent router is allowed to mount. Deliberately a literal:
# the point of this file is that adding to the agent's reach is a decision
# somebody has to write down, not something a new @router.post does quietly.
EXPECTED_ROUTES = {
    ("GET", "/agent/manifest"),
    ("POST", "/agent/parse-recipe-source"),
    ("POST", "/agent/search-recipes"),
    ("GET", "/agent/recipes/{recipe_id}"),
    ("POST", "/agent/recipe-drafts"),
    ("GET", "/agent/recipe-drafts/{draft_id}"),
    ("PATCH", "/agent/recipe-drafts/{draft_id}"),
    ("POST", "/agent/suggest-meal-plan"),
    ("POST", "/agent/meal-plan-drafts"),
}


def mounted_routes():
    from app.routers.agent import router

    return {
        (method, route.path)
        for route in router.routes
        for method in route.methods
        if method != "HEAD"
    }


def test_the_agent_surface_is_exactly_this(agent):
    assert mounted_routes() == EXPECTED_ROUTES


def test_nothing_is_mounted_outside_the_agent_prefix(agent):
    """A route defined here with an absolute path would escape the prefix and,
    with it, the require_agent dependency reasoning above."""
    assert all(path.startswith("/agent/") for _, path in mounted_routes())


def test_the_manifest_lists_every_mounted_tool(agent):
    """The manifest is what the agent is configured from. A tool that exists
    but isn't listed is one nobody knows the rules for."""
    from app.routers.agent import TOOLS

    described = {(t.method, t.path) for t in TOOLS}
    assert described == mounted_routes()


def test_the_manifest_says_what_the_agent_cannot_do(agent):
    body = agent.get("/agent/manifest").json()

    assert body["contract_version"] >= 1
    assert body["guarantees"]
    # Writes are marked as such; the agent shouldn't have to infer which of
    # its tools change anything.
    writing = {t["name"] for t in body["tools"] if t["writes"]}
    # Every one of them creates or edits a draft. Nothing here writes a
    # recipe, a meal plan entry or a shopping list.
    assert writing == {"create_recipe_draft", "update_recipe_draft", "create_meal_plan_draft"}


def test_promotion_is_not_on_this_surface(agent, draft_payload):
    """The one that matters. Promotion is the only route from a draft into the
    cookbook, and it is John's."""
    draft = agent.post("/drafts", json=draft_payload).json()

    assert agent.post(f"/agent/drafts/{draft['id']}/promote").status_code == 404
    assert agent.post(f"/agent/recipe-drafts/{draft['id']}/promote").status_code == 404


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/agent/recipes"),
        ("delete", "/agent/recipes/00000000-0000-0000-0000-000000000000"),
        ("post", "/agent/meal-plan"),
        ("post", "/agent/shopping-list"),
        ("post", "/agent/backup/restore"),
        ("get", "/agent/backup/export"),
        ("post", "/agent/pantry"),
        ("post", "/agent/aisles/rules"),
    ],
)
def test_the_agent_cannot_reach_the_rest_of_the_app(agent, method, path):
    # 404 for a path that isn't mounted, 405 for a path that is but not for
    # this verb -- DELETE /agent/recipes/{id} is the second kind. Either way
    # there is no handler, which is the claim.
    assert getattr(agent, method)(path).status_code in (404, 405)


# --------------------------------------------------------------------------
# parse_recipe_source
# --------------------------------------------------------------------------


def test_parsing_text_returns_structure_and_stores_nothing(agent):
    response = agent.post(
        "/agent/parse-recipe-source",
        json={"text": "Beans on toast\n\n400g baked beans\n2 slices bread\n\nHeat the beans."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "paste"
    assert body["payload"]["title"] == "Beans on toast"
    assert [i["name"] for i in body["payload"]["ingredients"]] == ["baked beans", "bread"]
    # Nothing was written: this is a reading tool.
    assert agent.get("/drafts").json() == []
    assert agent.get("/recipes").json() == []


def test_the_source_text_comes_back_with_the_parse(agent):
    """So the agent can quote what it read rather than paraphrase it."""
    text = "Toast\n\n2 slices bread\n\nToast the bread."

    body = agent.post("/agent/parse-recipe-source", json={"text": text}).json()

    assert body["source_text"] == text


def test_parsing_reports_what_it_is_unsure_about(agent):
    """The parser's own doubts, handed over rather than hidden. A draft with a
    blank title is worth the agent fixing before it proposes it."""
    body = agent.post("/agent/parse-recipe-source", json={"text": "just some words"}).json()

    assert body["issues"]


def test_text_and_url_together_are_refused(agent):
    response = agent.post(
        "/agent/parse-recipe-source",
        json={"text": "beans", "url": "https://example.test/r"},
    )

    assert response.status_code == 400


def test_neither_text_nor_url_is_refused(agent):
    assert agent.post("/agent/parse-recipe-source", json={}).status_code == 400


def test_blank_text_is_refused(agent):
    assert agent.post("/agent/parse-recipe-source", json={"text": "   "}).status_code == 400


def test_a_private_url_is_still_refused_for_the_agent(agent):
    """The SSRF guard is not relaxed because the caller is trusted. The agent
    is handed links by strangers; that is exactly the case the guard is for."""
    response = agent.post(
        "/agent/parse-recipe-source", json={"url": "http://127.0.0.1:8000/secrets"}
    )

    assert response.status_code == 400
    assert "private" in response.json()["detail"].lower() or "loopback" in response.json()["detail"].lower()


def test_a_non_http_url_is_refused(agent):
    assert agent.post("/agent/parse-recipe-source", json={"url": "ftp://example.test/r"}).status_code == 422


# --------------------------------------------------------------------------
# search_recipes
# --------------------------------------------------------------------------


@pytest.fixture
def library(client, recipe_payload):
    """A small library with enough variety to tell the filters apart."""
    made = {}
    for title, extra in [
        ("Quick Pasta", {"tags": ["italian"], "prep_time": 5, "cook_time": 10, "estimated_cost": 6}),
        ("Slow Stew", {"tags": ["comfort"], "prep_time": 20, "cook_time": 160, "estimated_cost": 18}),
        ("Cheap Rice", {"tags": ["thai"], "prep_time": 5, "cook_time": 15, "estimated_cost": 4}),
        # No cost at all, which is a different thing from cheap.
        ("Unpriced Thing", {"tags": ["italian"], "prep_time": 5, "cook_time": 5, "estimated_cost": None}),
    ]:
        made[title] = client.post(
            "/recipes", json={**recipe_payload, "title": title, **extra}
        ).json()
    return made


def titles(response):
    return {r["title"] for r in response.json()["results"]}


def test_an_empty_search_returns_the_library(agent, library):
    """A search tool that returns nothing by default teaches its caller to stop
    trusting it."""
    response = agent.post("/agent/search-recipes", json={})

    assert response.status_code == 200
    assert len(response.json()["results"]) == 4


def test_total_matched_is_counted_before_the_limit(agent, library):
    """Otherwise the agent can't tell "the only two that fit" from "two of
    forty", and those deserve different answers."""
    body = agent.post("/agent/search-recipes", json={"limit": 2}).json()

    assert len(body["results"]) == 2
    assert body["total_matched"] == 4


def test_filtering_by_time(agent, library):
    assert titles(agent.post("/agent/search-recipes", json={"max_total_time": 30})) == {
        "Quick Pasta",
        "Cheap Rice",
        "Unpriced Thing",
    }


def test_filtering_by_cost_excludes_the_unpriced(agent, library):
    """Unlike time, a missing cost is not treated as zero. The point of a
    budget search is not to be surprised at the till, and an unpriced recipe is
    not evidence of being cheap."""
    assert titles(agent.post("/agent/search-recipes", json={"max_cost": 10})) == {
        "Quick Pasta",
        "Cheap Rice",
    }


def test_tags_are_any_of(agent, library):
    assert titles(agent.post("/agent/search-recipes", json={"tags": ["thai", "comfort"]})) == {
        "Cheap Rice",
        "Slow Stew",
    }


def test_ingredients_are_all_of(agent, library, client, recipe_payload):
    """"Use up the chicken and the rice" means a recipe wanting both."""
    only_zucchini = {**recipe_payload, "title": "Zucchini Only",
                     "ingredients": [{"name": "zucchini", "category": "raw_ingredient"}]}
    client.post("/recipes", json=only_zucchini)

    both = titles(agent.post("/agent/search-recipes", json={"includes_ingredients": ["zucchini", "apple"]}))

    assert "Zucchini Only" not in both
    assert "Quick Pasta" in both


def test_never_cooked(agent, library):
    agent.post(f"/recipes/{library['Quick Pasta']['id']}/cooked", json={"cooked_on": "2026-09-01"})

    assert "Quick Pasta" not in titles(agent.post("/agent/search-recipes", json={"never_cooked": True}))


def test_not_cooked_since_includes_the_never_cooked(agent, library):
    """Never is the extreme case of a long time ago, not a missing answer."""
    agent.post(f"/recipes/{library['Quick Pasta']['id']}/cooked", json={"cooked_on": "2026-09-20"})

    found = titles(agent.post("/agent/search-recipes", json={"not_cooked_since": "2026-09-10"}))

    assert "Quick Pasta" not in found
    assert "Slow Stew" in found


def test_the_summary_carries_what_a_choice_is_made_of(agent, library):
    body = agent.post("/agent/search-recipes", json={"text": "Quick Pasta"}).json()

    (found,) = body["results"]
    assert found["total_time"] == 15
    assert found["times_cooked"] == 0
    assert found["last_cooked_on"] is None


def test_an_unknown_sort_is_refused_rather_than_ignored(agent, library):
    """Silently falling back would hand the agent a differently-ordered list
    than it asked for and no way to tell."""
    response = agent.post("/agent/search-recipes", json={"sort": "vibes"})

    assert response.status_code == 400
    assert "sort" in response.json()["detail"]


# --------------------------------------------------------------------------
# get_recipe
# --------------------------------------------------------------------------


def test_reading_one_recipe_in_full(agent, library):
    recipe = agent.get(f"/agent/recipes/{library['Quick Pasta']['id']}").json()

    assert recipe["title"] == "Quick Pasta"
    assert [i["name"] for i in recipe["ingredients"]] == ["zucchini", "apple", "black pepper"]
    assert recipe["steps"]


def test_reading_a_missing_recipe(agent):
    assert agent.get("/agent/recipes/00000000-0000-0000-0000-000000000000").status_code == 404
