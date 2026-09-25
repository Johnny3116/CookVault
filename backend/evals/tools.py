"""The tool schemas Qwen is shown, generated rather than transcribed.

The request models already exist in `app.schemas_agent`, because Phase 2
built that surface. Their JSON Schema comes straight out of
`model_json_schema()`, so a field renamed in the contract is renamed here on
the next run and cannot silently drift into a tool description that lies.

`get_recipe` is the one exception and is marked as such below.

The generated schema is then **flattened**. Pydantic writes an optional field
as `anyOf: [{"type": "string"}, {"type": "null"}]`, which is correct and which
small local models handle badly -- and optionality is already carried by the
`required` list, so the union says nothing the schema doesn't. Titles and
defaults come out too; neither helps a model decide what to pass, and both are
tokens in a context window that has better uses.
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel, Field

from app import schemas_agent as sa
from app.services import recipe_search


# `get_meal_plan` used to be a hand-written copy here, because the route did
# not exist on the agent surface. It does now (`GET /agent/meal-plan`), and
# its request model lives in the contract like the others. Re-exported so the
# harness's tests keep one name for it.
GetMealPlanRequest = sa.GetMealPlanRequest


class GetRecipeRequest(BaseModel):
    """Also provisional, for a different reason: `GET /agent/recipes/{id}` takes
    its argument in the path, so there is no request model to generate from.
    The one field is the path parameter."""

    recipe_id: str = Field(description="The recipe's id, as returned by search_recipes.")


# When a union survives having its null branch removed, this is the order the
# remaining branch is chosen in. It exists for `Decimal`, which Pydantic renders
# as `number | string`, the string branch carrying a regex -- offer a small model
# both and it will send a string about half the time, and then every consumer
# has to cope with two shapes for one number.
_TYPE_PREFERENCE = ("number", "integer", "string", "boolean", "array", "object")


def _collapse_union(node: Any) -> Any:
    """`anyOf: [T, null]` -> T. Optionality lives in `required`, not in a union."""
    if not isinstance(node, dict):
        return node
    options = node.get("anyOf")
    if not isinstance(options, list):
        return node

    concrete = [o for o in options if isinstance(o, dict) and o.get("type") != "null"]
    if not concrete:
        return node
    chosen = min(
        concrete,
        key=lambda o: _TYPE_PREFERENCE.index(o["type"])
        if o.get("type") in _TYPE_PREFERENCE
        else len(_TYPE_PREFERENCE),
    )
    merged = {**{k: v for k, v in node.items() if k != "anyOf"}, **chosen}
    return _collapse_union(merged)


def _inline_defs(node: Any, defs: dict[str, Any]) -> Any:
    """Resolve `$ref` into the schema. A model cannot follow a pointer."""
    if isinstance(node, list):
        return [_inline_defs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = copy.deepcopy(defs.get(ref.rsplit("/", 1)[-1], {}))
        target.update({k: v for k, v in node.items() if k != "$ref"})
        return _inline_defs(target, defs)
    return {key: _inline_defs(value, defs) for key, value in node.items()}


# Noise for a model choosing arguments: a title repeats the key, and a default
# invites it to send the default explicitly instead of omitting the field.
_DROP = ("title", "default")


def _prune(node: Any) -> Any:
    if isinstance(node, list):
        return [_prune(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = _collapse_union(node)
    return {key: _prune(value) for key, value in node.items() if key not in _DROP}


def schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """A model's JSON Schema, flattened for a small local model to read."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    flat = _prune(_inline_defs(raw, defs))
    flat.pop("description", None)  # the tool carries its own description
    return flat


def _enrich(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Constraints the contract knows but its JSON Schema doesn't carry.

    `sort` is a bare `str` on SearchRecipesRequest, validated by the router
    against `recipe_search.SORTS` -- correct for an API that wants to answer
    "sort must be one of..." but useless to a model, which will confidently
    invent `"relevance"`. The allowed values are read from the same tuple the
    router checks, so this cannot drift. Phase 1 should make the field a
    Literal in `schemas_agent` and this can go.
    """
    if name == "search_recipes":
        schema["properties"]["sort"]["enum"] = list(recipe_search.SORTS)
    return schema


def tool(name: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    """One entry in Ollama's `tools` list (the OpenAI function shape)."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": _enrich(name, schema_for(model)),
        },
    }


# The descriptions are what the model actually reads when choosing. Each says
# what the tool answers and, where it matters, what it does *not* -- the
# distinction between "which recipes use the chicken" and "what can I make from
# only these" is the kind of thing a model guesses wrong in a helpful direction.
TOOLS: list[dict[str, Any]] = [
    tool(
        "search_recipes",
        "Search the saved recipe library by tags, cooking time, cost, ingredients "
        "and cooking history. Use this to find recipes John already has. "
        "`includes_ingredients` finds recipes that USE those ingredients (for using "
        "something up); it does not find recipes makeable from only those.",
        sa.SearchRecipesRequest,
    ),
    tool(
        "get_recipe",
        "Read one saved recipe in full: ingredients, steps, alternates and where it "
        "came from. Needs an id from search_recipes; it cannot look a recipe up by name.",
        GetRecipeRequest,
    ),
    tool(
        "get_meal_plan",
        "Read what is already planned on the calendar for a date range. Use this "
        "before suggesting meals, so a week does not serve the same thing twice.",
        GetMealPlanRequest,
    ),
]

TOOL_NAMES = frozenset(entry["function"]["name"] for entry in TOOLS)
