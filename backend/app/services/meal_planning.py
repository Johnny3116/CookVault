"""Which recipes to suggest for a week, and why.

The spec asks auto-fill for "diverse, easy, tasty meals where a reasonable
grocery budget covers the week". Three of those four are arithmetic over data
CookVault already has, and one of them is not:

- **Diverse** is the cook log. How long since this was last made is a number.
- **Easy** and **within budget** are the time and cost filters.
- **Tasty** is not something this module can know, and it does not pretend to.

So the variety arithmetic lives here, deterministic and explainable, rather
than in whatever model is calling. A model asked to "avoid repeating staples"
will produce a plausible answer that quietly repeats staples, and nothing about
the answer will say so. A number of days since last cooked is checkable, and
every candidate comes back with the sentence that explains its score.

What the agent is actually for is the part left over: taste, balance across a
week, what suits a Tuesday, what John said last time. It gets ranked candidates
and makes those judgements -- which is a much better use of it than arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services import recipe_search

# Past this, "ages ago" and "even longer ago" stop being a meaningful
# difference. Without a cap a recipe last made two years ago would outrank
# everything else forever, which is not variety -- it is a different rut.
STALENESS_CAP_DAYS = 120

# Never-cooked sits at the top of the range rather than above it. It is the
# extreme case of a long time ago, not a separate kind of answer -- the same
# reasoning that puts never-cooked first in the library's "not made in ages".
NEVER_COOKED_SCORE = float(STALENESS_CAP_DAYS)

# Being planned already is a much stronger signal than being stale is: the
# point of the window penalty is that a week should not serve the same thing
# twice, and no amount of staleness should outvote that.
ALREADY_PLANNED_PENALTY = 1000.0

# A small nudge, not a thumb on the scale. Favourites should win ties, not
# crowd out the variety this whole module exists to produce.
FAVOURITE_BONUS = 5.0


@dataclass(frozen=True)
class Scored:
    recipe: models.Recipe
    score: float
    reason: str


def _staleness(recipe: models.Recipe, today: date) -> tuple[float, str]:
    if recipe.last_cooked_on is None:
        return NEVER_COOKED_SCORE, "never cooked"
    days = (today - recipe.last_cooked_on).days
    if days < 0:
        # A log entry dated in the future: someone recording Saturday's dinner
        # on Thursday. Treat it as cooked today rather than letting the
        # arithmetic make it maximally stale.
        return 0.0, "logged as cooked ahead of today"
    return float(min(days, STALENESS_CAP_DAYS)), f"not cooked in {days} days"


def rank(
    db: Session,
    *,
    on: date,
    window: tuple[date, date],
    max_total_time: int | None = None,
    max_cost: Decimal | None = None,
    tags: list[str] | None = None,
    exclude_recipe_ids: list | None = None,
) -> list[Scored]:
    """Every eligible recipe, best fit first.

    `window` is the span the plan covers: anything already planned inside it is
    pushed to the bottom rather than removed, because "you already have this on
    Thursday" is information, and a caller with four recipes and seven days
    still needs an answer.
    """
    filters = recipe_search.RecipeFilters(
        max_total_time=max_total_time,
        max_cost=max_cost,
        tags=tags or [],
        sort="title",  # a stable base order, so equal scores rank the same way twice
    )
    recipes = db.execute(recipe_search.build_query(filters)).scalars().all()

    excluded = set(exclude_recipe_ids or [])
    planned = {
        row.recipe_id
        for row in db.execute(
            select(models.MealPlanEntry).where(
                models.MealPlanEntry.date >= window[0],
                models.MealPlanEntry.date <= window[1],
            )
        ).scalars()
    }

    scored: list[Scored] = []
    for recipe in recipes:
        if recipe.id in excluded:
            continue
        score, reason = _staleness(recipe, on)
        if recipe.is_favorite:
            score += FAVOURITE_BONUS
            reason += ", a favourite"
        if recipe.id in planned:
            score -= ALREADY_PLANNED_PENALTY
            reason += ", but already on the plan this week"
        scored.append(Scored(recipe=recipe, score=score, reason=reason))

    # Sorted by score, then by title so a tie resolves the same way every time.
    # A suggester that returns a different order for the same data is one
    # nobody can debug.
    #
    # The title key is redundant today and kept anyway: the base query above
    # already orders by title and Python's sort is stable, so removing it
    # changes nothing and no test can tell. It stops determinism from being an
    # accident of those two facts lining up -- change the base sort and this is
    # what keeps the answer stable.
    scored.sort(key=lambda s: (-s.score, s.recipe.title))
    return scored


def deal(ranked: list[Scored], days: int, per_day: int) -> list[list[Scored]]:
    """Spread the ranked list across the days rather than repeating it.

    Handing every day the same top five would make "here are candidates for
    seven days" a list of five recipes, and a caller taking the first suggestion
    each day would cook the same thing all week. Dealing round-robin -- day 0
    gets ranks 0, n, 2n; day 1 gets 1, n+1, ... -- means taking the top
    suggestion for each day produces `days` different recipes, while every day
    still sees a spread of quality rather than the dregs.
    """
    if days <= 0:
        return []
    return [ranked[index::days][:per_day] for index in range(days)]


def dates_from(start: date, days: int) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(days)]
