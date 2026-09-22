"""Recipe scaling.

Scaling is nondestructive: the stored recipe stays canonical and quantities are
scaled at read time. The scale itself is derived from target servings rather
than stored as a multiplier, because "make this for 8" stays meaningful if the
recipe is later corrected to serve 6, while "scale = 2.0" silently becomes
wrong.
"""

from __future__ import annotations

from decimal import Decimal

ONE = Decimal(1)


def effective_scale(recipe_servings: int | None, target_servings: int | None) -> Decimal:
    """How much to multiply this recipe's quantities by.

    Falls back to 1 when either side is missing or nonsensical. A recipe that
    never recorded its own yield has no basis for scaling, and inventing one
    (assuming it serves four, say) would quietly produce wrong amounts on a
    shopping list. Callers that need to tell the difference should use
    `can_scale`.
    """
    if not recipe_servings or recipe_servings <= 0:
        return ONE
    if not target_servings or target_servings <= 0:
        return ONE
    return Decimal(target_servings) / Decimal(recipe_servings)


def can_scale(recipe_servings: int | None) -> bool:
    """Whether scaling this recipe is meaningful at all."""
    return bool(recipe_servings and recipe_servings > 0)


def scale_quantity(quantity: Decimal | None, scale: Decimal) -> Decimal | None:
    """Apply a scale to one quantity.

    An ingredient with no amount ("salt, to taste") has nothing to scale and
    stays amountless. No rounding happens here -- the result feeds further
    arithmetic, and quantizing mid-pipeline compounds error across a week of
    recipes. Round once, at the point of display or storage.
    """
    if quantity is None:
        return None
    if scale == ONE:
        return quantity
    return quantity * scale
