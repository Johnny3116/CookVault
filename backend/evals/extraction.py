"""The JSON schema Ollama's `format` constrains extraction to.

Built from `app.schemas.RecipeCreate` -- the same model that gates promotion --
with three deliberate differences.

**Fields the model may not set are removed.** `source_type`, `source_url` and
`is_favorite` are CookVault's to fill in: where a recipe came from is a fact
about the import, not something to read out of the text, and whether John likes
it is not a model's call.

**`unit` is an enum of what CookVault can convert.** This is the single best
reason to use constrained output here. An unrecognised unit is only a *warning*
in `services/drafts` -- "1 handful" is a real thing for a cook to write -- but
on an extracted draft it is usually invented. Enumerating the units turns the
most common hallucination from something to review into something the sampler
cannot emit.

**`category` is an enum**, for the same reason in a smaller way.

What the schema cannot express is step numbering: JSON Schema has no way to say
"`order` runs 1..n with no gaps or repeats". The existing text parser gets that
free by construction; a model will not, so the prompt asks for it explicitly.

Nothing in the harness re-checks it. `validate_payload` already treats a broken
sequence as an error and names the numbers it got, which is the separate,
actionable failure reason that was wanted -- "got the food right, numbered the
steps wrong" is a prompt fix and "invented an ingredient" is not. Importing the
real validator is what made that free.
"""

from __future__ import annotations

from typing import Any

from app import units
from app.models import IngredientCategory

# _CANONICAL is private. Reading it here is deliberate and guarded: the test
# `test_every_listed_unit_is_one_the_app_accepts` asserts each name below
# round-trips through the public `canonical_unit()`, so if the private shape
# moves, the eval fails loudly instead of constraining the model to units the
# app no longer knows. Phase 1 should export this properly and delete the note.
CANONICAL_UNITS: tuple[str, ...] = tuple(sorted(units._CANONICAL))

CATEGORIES: tuple[str, ...] = tuple(category.value for category in IngredientCategory)

# Fields of RecipeCreate the model is not allowed to decide.
OMITTED: frozenset[str] = frozenset({"source_type", "source_url", "is_favorite"})


INGREDIENT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "The ingredient alone, without the amount or the preparation. "
            "'2 cloves garlic, minced' is name 'garlic'.",
        },
        "quantity": {
            "type": ["number", "null"],
            "description": "The number only. Null if the source gives no amount.",
        },
        "unit": {
            "type": ["string", "null"],
            "enum": [*CANONICAL_UNITS, None],
            "description": "Null for a count of whole items, or when the source's unit "
            "is not in this list -- in that case leave the unit out rather than "
            "substituting a different one.",
        },
        "category": {"type": "string", "enum": list(CATEGORIES)},
    },
    "required": ["name", "category"],
}

STEP: dict[str, Any] = {
    "type": "object",
    "properties": {
        "order": {
            "type": "integer",
            "description": "1 for the first step, then 2, 3 and so on with no gaps.",
        },
        "instruction_text": {"type": "string"},
        "temperature": {"type": ["string", "null"]},
        "duration": {"type": ["string", "null"]},
        "notes": {"type": ["string", "null"]},
    },
    "required": ["order", "instruction_text"],
}

RECIPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "servings": {"type": ["integer", "null"]},
        "prep_time": {"type": ["integer", "null"], "description": "Minutes."},
        "cook_time": {"type": ["integer", "null"], "description": "Minutes."},
        "estimated_cost": {"type": ["number", "null"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "cook_methods": {"type": "array", "items": {"type": "string"}},
        "ingredients": {"type": "array", "items": INGREDIENT},
        "steps": {"type": "array", "items": STEP},
    },
    "required": ["title", "ingredients", "steps"],
}


def property_names() -> dict[str, set[str]]:
    """Every key this schema can produce, for the drift test."""
    return {
        "recipe": set(RECIPE_SCHEMA["properties"]),
        "ingredient": set(INGREDIENT["properties"]),
        "step": set(STEP["properties"]),
    }
