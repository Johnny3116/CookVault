"""Recipe scaling and the plan -> scale -> shop pipeline."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.scaling import can_scale, effective_scale, scale_quantity
from app.units import tidy

D = Decimal


@pytest.mark.parametrize(
    "recipe_servings,target,expected",
    [
        (4, 8, "2"), (4, 2, "0.5"), (4, 6, "1.5"), (4, 4, "1"),
        (3, 8, None),  # repeating; checked separately
        (6, 4, None),
    ],
)
def test_effective_scale(recipe_servings, target, expected):
    result = effective_scale(recipe_servings, target)
    if expected is not None:
        assert result == D(expected)
    else:
        assert result == D(target) / D(recipe_servings)


@pytest.mark.parametrize(
    "recipe_servings,target",
    [(None, 8), (0, 8), (-2, 8), (4, None), (4, 0), (4, -1)],
)
def test_scale_falls_back_to_one_when_it_cannot_be_derived(recipe_servings, target):
    """A recipe with no recorded yield has no basis to scale from. Assuming one
    would quietly produce wrong amounts on a shopping list."""
    assert effective_scale(recipe_servings, target) == D(1)


def test_can_scale_reports_whether_scaling_is_meaningful():
    assert can_scale(4) is True
    assert can_scale(None) is False
    assert can_scale(0) is False


def test_scaling_leaves_amountless_ingredients_alone():
    """"Salt, to taste" does not become "2 to taste"."""
    assert scale_quantity(None, D(2)) is None


def test_scaling_does_not_round_mid_pipeline():
    """Rounding here would compound across a week of recipes, so the value that
    comes back still carries full precision; the caller rounds once at the end."""
    result = scale_quantity(D("1"), effective_scale(3, 1))

    assert result != tidy(result), "scale_quantity must not quantize its result"
    assert tidy(result) == D("0.333")
    assert result.as_tuple().exponent < -10


def test_scaling_is_exact_for_thirds_through_the_round_trip():
    scale = effective_scale(3, 6)
    assert scale_quantity(D("0.333"), scale) == D("0.666")
