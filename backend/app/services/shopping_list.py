"""Turning planned recipes into a shopping list.

The pipeline, in order:

    planned recipe -> effective scale -> scale ingredients -> normalize units
    -> merge compatible quantities -> generated shopping items

Scaling and merging are both Decimal throughout and only round at the end, so
a week of half-batches doesn't accumulate rounding error.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from app import models
from app.services.scaling import effective_scale, scale_quantity
from app.units import Measure, merge


@dataclass(frozen=True)
class PlannedRecipe:
    """A recipe to buy for, and how many servings of it are wanted.

    `target_servings` of None means "as the recipe is written".
    """

    recipe: models.Recipe
    target_servings: int | None = None


@dataclass(frozen=True)
class GeneratedItem:
    name: str
    quantity: Decimal | None
    unit: str | None
    category: models.IngredientCategory
    recipe_id: object | None


def build_items(planned: Iterable[PlannedRecipe]) -> list[GeneratedItem]:
    """Collapse planned recipes into the lines you actually shop for.

    Ingredients are grouped by name and category -- the same word in two
    categories (olive oil as a pantry good in one recipe, a sauce in another)
    stays two lines, because merging them would put it in an arbitrary column.
    Within a group, `app.units.merge` decides what can be summed.
    """
    grouped: OrderedDict[tuple[str, models.IngredientCategory], dict] = OrderedDict()

    for entry in planned:
        scale = effective_scale(entry.recipe.servings, entry.target_servings)
        for ingredient in entry.recipe.ingredients:
            key = (ingredient.name.strip().lower(), ingredient.category)
            group = grouped.setdefault(
                key,
                {"name": ingredient.name.strip(), "measures": [], "recipe_ids": set()},
            )
            group["measures"].append(
                Measure(
                    quantity=scale_quantity(ingredient.quantity, scale),
                    unit=ingredient.unit,
                )
            )
            group["recipe_ids"].add(entry.recipe.id)

    items: list[GeneratedItem] = []
    for (_, category), group in grouped.items():
        # Provenance only survives when a single recipe contributed; a merged
        # line has no one recipe to attribute it to.
        sole_recipe = next(iter(group["recipe_ids"])) if len(group["recipe_ids"]) == 1 else None
        for measure in merge(group["measures"]):
            items.append(
                GeneratedItem(
                    name=group["name"],
                    quantity=measure.quantity,
                    unit=measure.unit,
                    category=category,
                    recipe_id=sole_recipe,
                )
            )
    return items
