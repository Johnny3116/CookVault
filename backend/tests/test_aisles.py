"""Aisle taxonomy: matching, precedence, overrides, and shop order.

Aisle is a different axis from ingredient category, and the tests that matter
are the ones pinning *which* rule wins, because that is where a mapping
quietly goes wrong: "chicken stock" landing in meat because "chicken" matched
first is exactly the failure this is built to avoid.
"""

from __future__ import annotations

import pytest

from app.models import ShoppingAisle
from app.services.aisles import AISLE_ORDER, Rule, match_rule, resolve_aisle

RULES = [
    Rule("chicken", ShoppingAisle.meat_seafood),
    Rule("chicken stock", ShoppingAisle.pantry),
    Rule("stock", ShoppingAisle.pantry),
    Rule("oil", ShoppingAisle.pantry),
    Rule("parsley", ShoppingAisle.produce),
    Rule("milk", ShoppingAisle.dairy_eggs),
    Rule("coconut milk", ShoppingAisle.pantry),
    Rule("ham", ShoppingAisle.meat_seafood),
]


def aisle_of(name: str) -> ShoppingAisle:
    return resolve_aisle(name, None, RULES)


# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("chicken thighs", ShoppingAisle.meat_seafood),
        ("parsley", ShoppingAisle.produce),
        ("olive oil", ShoppingAisle.pantry),
        ("semi-skimmed milk", ShoppingAisle.dairy_eggs),
    ],
)
def test_matching(name, expected):
    assert aisle_of(name) == expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("chicken stock", ShoppingAisle.pantry),
        ("organic chicken stock", ShoppingAisle.pantry),
        ("coconut milk", ShoppingAisle.pantry),
    ],
)
def test_the_more_specific_rule_wins(name, expected):
    """The whole point of the length tiebreak. "chicken stock" is a pantry
    item even though "chicken" is a rule and matches it."""
    assert aisle_of(name) == expected


def test_matching_is_whole_word():
    """"ham" must not fire on "hammer", and "oil" must not fire on "boiled"."""
    assert aisle_of("hammer") == ShoppingAisle.other
    assert aisle_of("boiled sweets") == ShoppingAisle.other


def test_multi_word_terms_need_consecutive_words():
    """"chicken and beef stock" contains both words but is not "chicken
    stock" -- it should fall to the single-word rules, not the pair."""
    rule = match_rule("chicken and beef stock", RULES)
    assert rule is not None and rule.term in {"chicken", "stock"}


def test_no_match_is_other_rather_than_a_guess():
    assert aisle_of("xylophone") == ShoppingAisle.other
    assert match_rule("xylophone", RULES) is None


def test_an_empty_name_matches_nothing():
    assert match_rule("", RULES) is None
    assert match_rule("   ", RULES) is None


def test_matching_ignores_case_and_punctuation():
    assert aisle_of("Chicken, free-range") == ShoppingAisle.meat_seafood


def test_an_override_beats_every_rule():
    """A person saying where it is in *their* shop is not something a rule
    should argue with."""
    assert resolve_aisle("chicken", ShoppingAisle.frozen, RULES) == ShoppingAisle.frozen


# --------------------------------------------------------------------------
# the rules API
# --------------------------------------------------------------------------


def test_the_seeded_rules_are_present_and_editable(client):
    rules = client.get("/aisles/rules").json()

    assert len(rules) > 100
    assert any(r["term"] == "chicken stock" and r["aisle"] == "pantry" for r in rules)
    # Seeded, not fixed: a starting point the user owns.
    target = next(r for r in rules if r["term"] == "chicken stock")
    assert client.delete(f"/aisles/rules/{target['id']}").status_code == 204


def test_resolve_says_which_rule_decided(client):
    """A mapping you can't interrogate is one you end up fighting."""
    body = client.get("/aisles/resolve", params={"name": "organic chicken stock"}).json()

    assert body["aisle"] == "pantry"
    assert body["matched_term"] == "chicken stock"


def test_resolve_admits_when_nothing_matched(client):
    body = client.get("/aisles/resolve", params={"name": "xylophone"}).json()

    assert body["aisle"] == "other"
    assert body["matched_term"] is None


def test_a_new_rule_takes_effect_immediately(client):
    assert client.get("/aisles/resolve", params={"name": "gochujang"}).json()["aisle"] == "other"

    client.post("/aisles/rules", json={"term": "gochujang", "aisle": "pantry"})

    assert (
        client.get("/aisles/resolve", params={"name": "gochujang"}).json()["aisle"] == "pantry"
    )


def test_duplicate_terms_are_refused(client):
    client.post("/aisles/rules", json={"term": "marmite", "aisle": "pantry"})

    second = client.post("/aisles/rules", json={"term": "marmite", "aisle": "other"})

    # Two rules for one word would make the winner depend on row order.
    assert second.status_code == 409


def test_a_blank_term_is_refused(client):
    assert client.post("/aisles/rules", json={"term": "   ", "aisle": "pantry"}).status_code == 400


def test_editing_a_rule_moves_everything_that_relied_on_it(client):
    """The reason the aisle is resolved per response instead of stored."""
    item = client.post("/shopping-list", json={"name": "chicken thighs"}).json()
    assert item["aisle"] == "meat_seafood"

    rule = next(r for r in client.get("/aisles/rules").json() if r["term"] == "chicken")
    client.patch(f"/aisles/rules/{rule['id']}", json={"aisle": "frozen"})

    assert client.get("/shopping-list").json()[0]["aisle"] == "frozen"


# --------------------------------------------------------------------------
# the shopping list
# --------------------------------------------------------------------------


def test_shopping_list_comes_back_in_shop_order(client):
    for name in ["bin bags", "milk", "chicken thighs", "onions", "bread"]:
        client.post("/shopping-list", json={"name": name})

    aisles = [item["aisle"] for item in client.get("/shopping-list").json()]

    assert aisles == sorted(aisles, key=AISLE_ORDER.index)
    assert aisles[0] == "produce"
    assert aisles[-1] == "household"


def test_an_item_can_be_moved_by_hand_and_moved_back(client):
    item = client.post("/shopping-list", json={"name": "chicken thighs"}).json()

    moved = client.patch(
        f"/shopping-list/{item['id']}", json={"aisle_override": "frozen"}
    ).json()
    assert moved["aisle"] == "frozen"
    assert moved["aisle_override"] == "frozen"

    # Clearing the override hands the line back to the rules.
    back = client.patch(f"/shopping-list/{item['id']}", json={"aisle_override": None}).json()
    assert back["aisle"] == "meat_seafood"
    assert back["aisle_override"] is None


def test_generated_items_get_aisles_too(client, recipe_payload):
    recipe = client.post("/recipes", json=recipe_payload).json()

    items = client.post("/shopping-list/generate", json={"recipe_ids": [recipe["id"]]}).json()

    assert all("aisle" in item for item in items)
    # recipe_payload has zucchini and apple, both produce.
    assert {i["aisle"] for i in items if i["name"] in ("zucchini", "apple")} == {"produce"}


def test_category_and_aisle_are_different_axes(client):
    """Fresh parsley is a spice_sauce *ingredient* in the produce *aisle*.
    Collapsing the two would lose one of them."""
    item = client.post(
        "/shopping-list", json={"name": "parsley", "category": "spice_sauce"}
    ).json()

    assert item["category"] == "spice_sauce"
    assert item["aisle"] == "produce"


def test_aisle_rules_require_auth(locked_client):
    assert locked_client.get("/aisles/rules").status_code == 401
    assert locked_client.post("/aisles/rules", json={"term": "x", "aisle": "pantry"}).status_code == 401
