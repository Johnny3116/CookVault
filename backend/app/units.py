"""Unit normalization.

Recipes mix cups, grams, ounces and millilitres inconsistently, and the
shopping list has to add them up. Spec section 7 calls this out as the trap to
solve early rather than retrofit, so quantities go through here rather than
being compared as free text.

Design notes:

- Conversions are *pure functions* over (quantity, unit) rather than extra
  columns on the tables. Storing a denormalized base quantity would need
  recomputing on every write and would silently drift the moment one path
  forgot; there is nothing here that a column would make materially faster for
  a single-user cookbook.
- Volumes are US customary (1 cup = 236.588 mL), not imperial. A US cook's
  "cup" is the one that matters here.
- Everything is Decimal. Float factors would turn 1/3 cup into noise that
  shows up in the rendered list.
- Unrecognized units are not an error. "2 cloves", "a pinch" and "to taste"
  are legitimate recipe entries; they simply don't convert, so they only merge
  with a textually identical unit.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Dimension = Literal["mass", "volume", "count"]

# Canonical unit -> (dimension, how many base units it is worth).
# Base units: gram for mass, millilitre for volume, one item for count.
_CANONICAL: dict[str, tuple[Dimension, Decimal]] = {
    # mass
    "mg": ("mass", Decimal("0.001")),
    "g": ("mass", Decimal("1")),
    "kg": ("mass", Decimal("1000")),
    "oz": ("mass", Decimal("28.349523125")),
    "lb": ("mass", Decimal("453.59237")),
    # volume (US customary)
    "ml": ("volume", Decimal("1")),
    "l": ("volume", Decimal("1000")),
    "tsp": ("volume", Decimal("4.92892159375")),
    "tbsp": ("volume", Decimal("14.78676478125")),
    "fl_oz": ("volume", Decimal("29.5735295625")),
    "cup": ("volume", Decimal("236.5882365")),
    "pt": ("volume", Decimal("473.176473")),
    "qt": ("volume", Decimal("946.352946")),
    "gal": ("volume", Decimal("3785.411784")),
    # count
    "ea": ("count", Decimal("1")),
}

# Spellings a person might actually type, mapped to the canonical unit.
_ALIASES: dict[str, str] = {
    "milligram": "mg", "milligrams": "mg", "mg": "mg",
    "gram": "g", "grams": "g", "g": "g", "gr": "g",
    "kilogram": "kg", "kilograms": "kg", "kg": "kg", "kilo": "kg", "kilos": "kg",
    "ounce": "oz", "ounces": "oz", "oz": "oz",
    "pound": "lb", "pounds": "lb", "lb": "lb", "lbs": "lb", "#": "lb",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "ml": "ml", "cc": "ml",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l", "l": "l",
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp", "tsps": "tsp", "t": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp", "tbsps": "tbsp",
    "tbs": "tbsp", "tb": "tbsp", "T": "tbsp",
    "fluid ounce": "fl_oz", "fluid ounces": "fl_oz", "fl oz": "fl_oz",
    "floz": "fl_oz", "fl_oz": "fl_oz",
    "cup": "cup", "cups": "cup", "c": "cup",
    "pint": "pt", "pints": "pt", "pt": "pt",
    "quart": "qt", "quarts": "qt", "qt": "qt",
    "gallon": "gal", "gallons": "gal", "gal": "gal",
    "each": "ea", "ea": "ea", "": "ea",
}

# The only unit changes worth making automatically: same measurement system,
# unambiguous, and only ever upward. Converting across systems to "tidy" a
# total is how 0.999 cup turns into 236.352 ml, which helps nobody.
_PROMOTIONS: dict[str, tuple[str, Decimal]] = {
    "g": ("kg", Decimal("1000")),
    "ml": ("l", Decimal("1000")),
}


def canonical_unit(raw: str | None) -> str | None:
    """Resolve a written unit to its canonical form, or None if unrecognized.

    `None` and `""` both mean "no unit given", which is a count of items.
    """
    if raw is None:
        return "ea"
    key = raw.strip().lower()
    # "T" means tablespoon while "t" means teaspoon, so check case-sensitively
    # before folding, otherwise one of them is lost.
    if raw.strip() in ("T", "t"):
        return _ALIASES[raw.strip()]
    key = key.rstrip(".")
    return _ALIASES.get(key)


def dimension_of(raw: str | None) -> Dimension | None:
    unit = canonical_unit(raw)
    return _CANONICAL[unit][0] if unit else None


def convert(quantity: Decimal, from_unit: str | None, to_unit: str) -> Decimal | None:
    """Convert between two units of the same dimension, or None if impossible."""
    source = canonical_unit(from_unit)
    target = canonical_unit(to_unit)
    if source is None or target is None:
        return None
    source_dim, source_factor = _CANONICAL[source]
    target_dim, target_factor = _CANONICAL[target]
    if source_dim != target_dim:
        return None
    return quantity * source_factor / target_factor


@dataclass(frozen=True)
class Measure:
    """A quantity with the unit it was written in.

    `quantity is None` means the recipe gave no amount ("salt, to taste").
    """

    quantity: Decimal | None
    unit: str | None


def _tidy(value: Decimal) -> Decimal:
    """Round to the 3 decimal places the NUMERIC(10,3) columns hold, then drop
    trailing zeros so 2.000 reads as 2."""
    rounded = value.quantize(Decimal("0.001"))
    normalized = rounded.normalize()
    # normalize() renders small integers in exponent form (2E+1); undo that.
    return normalized.quantize(Decimal(1)) if normalized == normalized.to_integral() else normalized


def _display_unit(total_in_base: Decimal, written_unit: str) -> str:
    """Keep the cook's own unit, promoting only within the same system.

    Three recipes' "1 cup" reads as 3 cup, and a third of a cup stays a third
    of a cup rather than becoming millilitres. Grams become kilograms (and
    millilitres litres) once the total is large enough to warrant it.
    """
    promotion = _PROMOTIONS.get(written_unit)
    if promotion is None:
        return written_unit
    larger, threshold = promotion
    return larger if total_in_base >= threshold else written_unit


def merge(measures: list[Measure]) -> list[Measure]:
    """Add up what can be added up.

    Measures sharing a dimension are summed and returned in the first one's
    unit (so cups stay cups), promoted up the ladder if the total has outgrown
    it. Measures whose units don't convert are grouped by the unit as written,
    and come back as separate entries. Entries with no quantity contribute
    nothing to a sum but keep the group alive, so "to taste" never invents a
    number.
    """
    # OrderedDict so output order follows input order, which is the order the
    # recipes were selected in.
    groups: OrderedDict[str, list[Measure]] = OrderedDict()
    for measure in measures:
        dimension = dimension_of(measure.unit)
        # Unrecognized units can only merge with the same literal spelling.
        key = dimension if dimension else f"raw:{(measure.unit or '').strip().lower()}"
        groups.setdefault(key, []).append(measure)

    merged: list[Measure] = []
    for key, group in groups.items():
        known = [m for m in group if m.quantity is not None]
        if not known:
            merged.append(Measure(quantity=None, unit=group[0].unit))
            continue

        if key.startswith("raw:"):
            total = sum((m.quantity for m in known), Decimal(0))
            merged.append(Measure(quantity=_tidy(total), unit=group[0].unit))
            continue

        base_total = Decimal(0)
        for m in known:
            unit = canonical_unit(m.unit)
            assert unit is not None
            base_total += m.quantity * _CANONICAL[unit][1]

        written = canonical_unit(known[0].unit)
        assert written is not None
        display = _display_unit(base_total, written)
        _, display_factor = _CANONICAL[display]
        # "ea" is an implementation detail for "no unit"; don't surface it if
        # the recipe didn't write one.
        display_label = None if display == "ea" and not (known[0].unit or "").strip() else display
        merged.append(Measure(quantity=_tidy(base_total / display_factor), unit=display_label))

    return merged
