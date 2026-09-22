"""One way to ask "which recipes match this?".

The library page and the agent's `search_recipes` tool want the same question
answered with different amounts of detail, so the query lives here and both
call it. Two near-identical query builders would agree for a while and then
quietly stop -- and the one that drifted would be the one the agent reasons
with.

What is deliberately *not* here: "what can I make from what I have". Answering
that needs to know a recipe requires nothing beyond the named ingredients,
which means quantity-tracked inventory, which CookVault deliberately does not
keep (see the pantry's docstring). `includes_ingredients` answers the question
that is actually answerable -- "which recipes use the chicken I need to use up"
-- and says so rather than approximating the other one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, nullsfirst, or_, select

from app import models

SORTS = ("updated", "last_cooked", "most_cooked", "title", "cost")


@dataclass(frozen=True)
class RecipeFilters:
    """Everything the library page and the agent can narrow by.

    Every field defaults to "don't care", so an empty filter set is the whole
    library rather than nothing -- a search tool that returns nothing by
    default teaches its caller to stop trusting it.
    """

    favorite: bool | None = None
    tags: list[str] = field(default_factory=list)
    cook_methods: list[str] = field(default_factory=list)
    includes_ingredients: list[str] = field(default_factory=list)
    max_total_time: int | None = None
    max_cost: Decimal | None = None
    text: str | None = None
    not_cooked_since: date | None = None
    never_cooked: bool = False
    sort: str = "updated"


def build_query(filters: RecipeFilters) -> Select:
    stmt = select(models.Recipe)

    if filters.favorite is not None:
        stmt = stmt.where(models.Recipe.is_favorite == filters.favorite)

    # Any-of within a facet, all-of across facets: "italian or thai, and on the
    # stovetop" is what a person means by ticking two cuisines and one method.
    if filters.tags:
        stmt = stmt.where(or_(*(models.Recipe.tags.contains([t]) for t in filters.tags)))
    if filters.cook_methods:
        stmt = stmt.where(
            or_(*(models.Recipe.cook_methods.contains([m]) for m in filters.cook_methods))
        )

    if filters.max_total_time is not None:
        # A recipe recording neither time counts as 0 rather than being
        # excluded: an unknown time is not a long one, and dropping untimed
        # recipes would hide most of a young library.
        total = func.coalesce(models.Recipe.prep_time, 0) + func.coalesce(models.Recipe.cook_time, 0)
        stmt = stmt.where(total <= filters.max_total_time)

    if filters.max_cost is not None:
        # Unknown cost is *not* treated as free. Unlike time, a missing cost
        # under a budget filter would be a claim the data does not support, and
        # the whole point of a budget search is not to be surprised at the till.
        #
        # The IS NOT NULL is redundant and kept anyway: `NULL <= 10` is NULL,
        # not true, so Postgres already drops unpriced rows. Removing the line
        # changes no result and no test can tell -- it is here to say out loud
        # that excluding them is the intent, not an accident of three-valued
        # logic that the next person might "fix" with a coalesce.
        stmt = stmt.where(models.Recipe.estimated_cost.is_not(None))
        stmt = stmt.where(models.Recipe.estimated_cost <= filters.max_cost)

    if filters.text and filters.text.strip():
        stmt = stmt.where(models.Recipe.title.ilike(f"%{filters.text.strip()}%"))

    for name in filters.includes_ingredients:
        term = name.strip()
        if not term:
            continue
        # All-of: each named ingredient adds another EXISTS. "chicken and rice"
        # means a recipe using both, which is the shape of "use up what's in
        # the fridge".
        stmt = stmt.where(
            select(models.Ingredient.id)
            .where(models.Ingredient.recipe_id == models.Recipe.id)
            .where(models.Ingredient.name.ilike(f"%{term}%"))
            .exists()
        )

    if filters.never_cooked:
        stmt = stmt.where(models.Recipe.last_cooked_on.is_(None))
    elif filters.not_cooked_since is not None:
        # Never-cooked satisfies "not since": never is the extreme case of a
        # long time ago, not a missing answer.
        stmt = stmt.where(
            or_(
                models.Recipe.last_cooked_on.is_(None),
                models.Recipe.last_cooked_on < filters.not_cooked_since,
            )
        )

    return _ordered(stmt, filters.sort)


def _ordered(stmt: Select, sort: str) -> Select:
    if sort == "last_cooked":
        # "What haven't I made in ages." Never-cooked sorts first, for the same
        # reason it satisfies not_cooked_since.
        return stmt.order_by(nullsfirst(models.Recipe.last_cooked_on.asc()), models.Recipe.title)
    if sort == "most_cooked":
        return stmt.order_by(models.Recipe.times_cooked.desc(), models.Recipe.title)
    if sort == "title":
        return stmt.order_by(models.Recipe.title)
    if sort == "cost":
        # Costed recipes first: a budget sort that leads with unpriced recipes
        # is answering a different question than the one asked.
        return stmt.order_by(models.Recipe.estimated_cost.asc().nulls_last(), models.Recipe.title)
    return stmt.order_by(models.Recipe.updated_at.desc())
