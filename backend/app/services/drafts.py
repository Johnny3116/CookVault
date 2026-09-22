"""Validation and promotion for recipe drafts.

This is the middle term of "AI proposes, CookVault validates, John approves".
It runs the same way whether the proposal was typed by hand or produced by a
model, which is the point: the door into the cookbook is one door.

Validation is deliberately two-layered.

*Structure* is Pydantic's job -- can this payload become a RecipeCreate at
all. A model that emits `"quantity": "about two"` fails here.

*Sense* is this module's job, and it is the layer that actually earns its
keep. A payload can parse perfectly and still be useless: no ingredients, no
steps, steps numbered 1, 2, 2, 5. Those are errors. Separately there are
things that are suspicious rather than wrong -- an unrecognised unit, the same
ingredient listed twice -- which are the classic shapes of a bad extraction
and exactly what a reviewer should look at. Those are warnings, and they do
not block promotion: "a handful of parsley" is a real thing to write.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from app import schemas
from app.units import canonical_unit

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class DraftIssue:
    severity: Severity
    field: str
    message: str


def _structural_issues(payload: dict[str, Any]) -> tuple[list[DraftIssue], schemas.RecipeCreate | None]:
    try:
        return [], schemas.RecipeCreate.model_validate(payload)
    except ValidationError as exc:
        issues = [
            DraftIssue(
                severity="error",
                # "ingredients -> 2 -> quantity" points at the offending line,
                # which is the whole reason for reporting per-field.
                field=" -> ".join(str(part) for part in error["loc"]) or "payload",
                message=error["msg"],
            )
            for error in exc.errors()
        ]
        return issues, None


def _sense_issues(recipe: schemas.RecipeCreate) -> list[DraftIssue]:
    issues: list[DraftIssue] = []

    if not recipe.title.strip():
        issues.append(DraftIssue("error", "title", "A recipe needs a title."))

    if not recipe.ingredients:
        issues.append(DraftIssue("error", "ingredients", "A recipe needs at least one ingredient."))
    if not recipe.steps:
        issues.append(DraftIssue("error", "steps", "A recipe needs at least one step."))

    # Steps are displayed and cooked in order, so the numbering has to be a
    # real sequence. Duplicates silently collapse in the UI and gaps read as a
    # missing instruction -- both are worse than a rejected draft.
    orders = [step.order for step in recipe.steps]
    if orders and sorted(orders) != list(range(1, len(orders) + 1)):
        issues.append(
            DraftIssue(
                "error",
                "steps",
                f"Step numbers must run 1..{len(orders)} with no gaps or repeats; got {sorted(orders)}.",
            )
        )

    if recipe.servings is not None and recipe.servings <= 0:
        issues.append(DraftIssue("error", "servings", "Servings must be greater than zero."))
    for field in ("prep_time", "cook_time"):
        value = getattr(recipe, field)
        if value is not None and value < 0:
            issues.append(DraftIssue("error", field, "Time cannot be negative."))

    for index, ingredient in enumerate(recipe.ingredients):
        where = f"ingredients -> {index}"
        if not ingredient.name.strip():
            issues.append(DraftIssue("error", where, "An ingredient needs a name."))
        if ingredient.quantity is not None and ingredient.quantity < 0:
            issues.append(DraftIssue("error", where, "Quantity cannot be negative."))
        # Not an error: "1 handful" is a legitimate thing for a cook to write.
        # But it will not convert or merge in the shopping list, and on an
        # extracted draft it is often a hallucinated unit -- worth a look.
        if ingredient.unit and canonical_unit(ingredient.unit) is None:
            issues.append(
                DraftIssue(
                    "warning",
                    where,
                    f"Unit {ingredient.unit!r} isn't one CookVault can convert, "
                    "so it won't merge in the shopping list.",
                )
            )

    duplicates = [
        name
        for name, count in Counter(i.name.strip().lower() for i in recipe.ingredients if i.name.strip()).items()
        if count > 1
    ]
    for name in duplicates:
        issues.append(
            DraftIssue("warning", "ingredients", f"{name!r} is listed more than once.")
        )

    return issues


def validate_payload(payload: dict[str, Any]) -> list[DraftIssue]:
    """Every problem with a proposed recipe, worst layer first.

    Structural failures stop the pass: there is no point complaining that a
    recipe has no steps when `steps` did not parse as a list in the first
    place, and the second message would only bury the first.
    """
    structural, recipe = _structural_issues(payload)
    if recipe is None:
        return structural
    return _sense_issues(recipe)


def has_errors(issues: list[DraftIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
