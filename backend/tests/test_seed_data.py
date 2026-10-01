"""The starter recipe set has to pass the same gate as anything else.

The seed script only creates drafts, so a broken entry would not reach the
cookbook -- but it would arrive in the review queue already failing, which is
a bad first impression and easy to prevent here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.drafts import validate_payload

SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "starter_recipes.json"
RECIPES = json.loads(SEED_FILE.read_text(encoding="utf-8"))


def test_titles_are_unique() -> None:
    titles = [r["title"].strip().lower() for r in RECIPES]
    assert len(titles) == len(set(titles))


@pytest.mark.parametrize("recipe", RECIPES, ids=[r["title"] for r in RECIPES])
def test_recipe_validates_cleanly(recipe: dict) -> None:
    # Warnings count too: an unconvertible unit or a duplicated ingredient
    # would split or double a shopping-list line.
    assert validate_payload(recipe) == []


@pytest.mark.parametrize("recipe", RECIPES, ids=[r["title"] for r in RECIPES])
def test_ingredient_names_are_shoppable(recipe: dict) -> None:
    # The shopping list merges on name, so preparation ("minced", "sliced")
    # belongs in the steps; otherwise one item becomes several lines.
    prep_words = ("minced", "sliced", "chopped", "grated", "melted", "cubes", "diced")
    for ingredient in recipe["ingredients"]:
        name = ingredient["name"].lower()
        assert not any(word in name for word in prep_words), ingredient["name"]
        assert "water" not in name, "water is not something to buy"
