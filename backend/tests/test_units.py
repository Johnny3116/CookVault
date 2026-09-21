"""Unit normalization.

Conversion errors here would quietly corrupt every shopping list, so these
pin the arithmetic as well as the behavior.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.units import Measure, canonical_unit, convert, dimension_of, merge

D = Decimal


@pytest.mark.parametrize(
    "written,expected",
    [
        ("g", "g"), ("gram", "g"), ("Grams", "g"), ("  G  ", "g"),
        ("kg", "kg"), ("kilos", "kg"),
        ("oz", "oz"), ("Ounces", "oz"),
        ("lb", "lb"), ("lbs", "lb"), ("pound", "lb"),
        ("ml", "ml"), ("milliliters", "ml"),
        ("l", "l"), ("Litre", "l"),
        ("tsp", "tsp"), ("teaspoon", "tsp"), ("tsp.", "tsp"),
        ("tbsp", "tbsp"), ("Tablespoons", "tbsp"), ("tbs", "tbsp"),
        ("cup", "cup"), ("Cups", "cup"), ("c", "cup"),
        ("fl oz", "fl_oz"), ("fluid ounces", "fl_oz"),
        ("qt", "qt"), ("gallon", "gal"),
        ("", "ea"), (None, "ea"), ("each", "ea"),
    ],
)
def test_alias_resolution(written, expected):
    assert canonical_unit(written) == expected


def test_capital_t_is_tablespoon_and_lowercase_t_is_teaspoon():
    """Standard recipe shorthand, and the one place case actually matters."""
    assert canonical_unit("T") == "tbsp"
    assert canonical_unit("t") == "tsp"


@pytest.mark.parametrize("written", ["clove", "cloves", "pinch", "to taste", "sprig", "bunch"])
def test_unrecognized_units_are_not_an_error(written):
    """These are legitimate recipe entries; they just don't convert."""
    assert canonical_unit(written) is None
    assert dimension_of(written) is None


@pytest.mark.parametrize(
    "quantity,source,target,expected",
    [
        ("1", "kg", "g", "1000"),
        ("1000", "g", "kg", "1"),
        ("1", "lb", "oz", "16"),
        ("1", "oz", "g", "28.349523125"),
        ("1", "cup", "ml", "236.5882365"),
        ("1", "cup", "tbsp", "16"),
        ("3", "tsp", "tbsp", "1"),
        ("1", "gal", "qt", "4"),
        ("2", "pt", "qt", "1"),
        ("1", "l", "ml", "1000"),
    ],
)
def test_conversion_arithmetic(quantity, source, target, expected):
    # These factors are exact in Decimal, so this is an exact comparison.
    assert convert(D(quantity), source, target) == D(expected)


def test_conversion_across_dimensions_is_refused():
    """Grams of flour are not millilitres of flour without a density."""
    assert convert(D("1"), "g", "ml") is None
    assert convert(D("1"), "cup", "lb") is None


def test_conversion_of_an_unknown_unit_is_refused():
    assert convert(D("1"), "clove", "g") is None


def test_same_unit_sums_stay_in_that_unit():
    result = merge([Measure(D("1"), "cup"), Measure(D("2"), "cup")])
    assert result == [Measure(D("3"), "cup")]


def test_compatible_units_sum_into_the_first_unit_written():
    """A cook who wrote cups should get cups back, not millilitres."""
    result = merge([Measure(D("1"), "cup"), Measure(D("2"), "tbsp")])
    assert len(result) == 1
    assert result[0].unit == "cup"
    assert result[0].quantity == D("1.125")  # 2 tbsp = 1/8 cup


def test_mass_sums_promote_to_kg_once_they_outgrow_grams():
    result = merge([Measure(D("600"), "g"), Measure(D("700"), "g")])
    assert result == [Measure(D("1.3"), "kg")]


def test_small_mass_sums_stay_in_grams():
    result = merge([Measure(D("100"), "g"), Measure(D("50"), "g")])
    assert result == [Measure(D("150"), "g")]


def test_incompatible_dimensions_stay_separate():
    """2 cloves of garlic plus 1 tbsp of garlic paste is two shopping lines."""
    result = merge([Measure(D("2"), "cloves"), Measure(D("1"), "tbsp")])
    assert len(result) == 2
    assert {(m.quantity, m.unit) for m in result} == {(D("2"), "cloves"), (D("1"), "tbsp")}


def test_identical_unrecognized_units_still_sum():
    result = merge([Measure(D("2"), "cloves"), Measure(D("3"), "cloves")])
    assert result == [Measure(D("5"), "cloves")]


def test_unitless_counts_merge_without_inventing_a_unit():
    result = merge([Measure(D("2"), None), Measure(D("1"), "")])
    assert len(result) == 1
    assert result[0].quantity == D("3")
    assert result[0].unit is None


def test_missing_quantities_never_invent_a_number():
    """"Salt, to taste" twice is still "to taste", not 0 or 2."""
    result = merge([Measure(None, "pinch"), Measure(None, "pinch")])
    assert result == [Measure(None, "pinch")]


def test_a_missing_quantity_alongside_a_real_one_keeps_the_real_one():
    result = merge([Measure(D("2"), "tsp"), Measure(None, "tsp")])
    assert result == [Measure(D("2"), "tsp")]


def test_thirds_do_not_accumulate_float_noise():
    """The reason factors are Decimal and not float."""
    result = merge([Measure(D("0.333"), "cup")] * 3)
    assert result[0].quantity == D("0.999")
    assert result[0].unit == "cup"
    assert "e" not in str(result[0].quantity).lower()


def test_a_partial_cup_stays_a_cup():
    """Regression: the display ladder used to demote anything under one cup
    into millilitres, so half a cup of milk read as 118.294 ml."""
    result = merge([Measure(D("0.25"), "cup"), Measure(D("0.25"), "cup")])
    assert result == [Measure(D("0.5"), "cup")]


def test_millilitres_promote_to_litres():
    result = merge([Measure(D("600"), "ml"), Measure(D("700"), "ml")])
    assert result == [Measure(D("1.3"), "l")]


def test_whole_numbers_render_without_trailing_zeros():
    result = merge([Measure(D("1.000"), "cup"), Measure(D("1.000"), "cup")])
    assert str(result[0].quantity) == "2"


def test_merge_preserves_input_order():
    result = merge([Measure(D("1"), "cloves"), Measure(D("1"), "g"), Measure(D("1"), "sprig")])
    assert [m.unit for m in result] == ["cloves", "g", "sprig"]
