"""Which aisle a shopping-list line belongs to.

The mapping is data, not code: rules live in `aisle_rules` and are edited at
runtime, because the right answer is personal and shop-specific. This module
only decides how a name is matched against them.

Resolution is deliberately dull and explainable:

1. An item's `aisle_override` wins outright. A human saying "this is in the
   world food aisle in my shop" is not something a rule should argue with.
2. Otherwise the longest matching term wins. "chicken stock" beating "chicken"
   is the whole reason length is the tiebreak -- stock is a pantry item and
   chicken is not, and the more specific rule is the one that knows.
3. No match is `other`, not a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import ShoppingAisle


@dataclass(frozen=True)
class Rule:
    term: str
    aisle: ShoppingAisle


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def match_rule(name: str, rules: list[Rule]) -> Rule | None:
    """The rule that claims `name`, or None.

    Terms match on whole-word boundaries, so "oil" does not fire on "boiled"
    and "ham" does not fire on "hammer". A multi-word term has to appear as a
    consecutive run of words.

    Returning the rule rather than just the aisle is what lets the API say
    *why* something landed where it did -- a surprising answer should be
    traceable to the row that caused it.
    """
    haystack = _words(name)
    if not haystack:
        return None

    best: tuple[int, Rule] | None = None
    for rule in rules:
        needle = _words(rule.term)
        if not needle:
            continue
        # A run of words, so "chicken stock" matches "organic chicken stock"
        # but not "chicken and beef stock".
        found = any(
            haystack[i : i + len(needle)] == needle
            for i in range(len(haystack) - len(needle) + 1)
        )
        if not found:
            continue
        # Longer terms are more specific: "chicken stock" must beat "chicken".
        weight = len(needle) * 1000 + len(rule.term)
        if best is None or weight > best[0]:
            best = (weight, rule)

    return best[1] if best else None


def match_aisle(name: str, rules: list[Rule]) -> ShoppingAisle | None:
    rule = match_rule(name, rules)
    return rule.aisle if rule else None


def resolve_aisle(
    name: str, override: ShoppingAisle | None, rules: list[Rule]
) -> ShoppingAisle:
    """The aisle to show for a line, override included."""
    if override is not None:
        return override
    return match_aisle(name, rules) or ShoppingAisle.other


# The order a shop is usually walked, so the list reads as a route rather than
# as an alphabetical jumble. `other` last because it is the "ask someone" pile.
AISLE_ORDER: list[ShoppingAisle] = [
    ShoppingAisle.produce,
    ShoppingAisle.meat_seafood,
    ShoppingAisle.dairy_eggs,
    ShoppingAisle.bakery,
    ShoppingAisle.frozen,
    ShoppingAisle.pantry,
    ShoppingAisle.drinks,
    ShoppingAisle.household,
    ShoppingAisle.other,
]


def aisle_sort_key(aisle: ShoppingAisle) -> int:
    return AISLE_ORDER.index(aisle)
