"""Whole-library export and restore.

A backup is only worth what a restore can prove, so the shape here is chosen
to make restoring verifiable rather than to look tidy:

- **Ids are preserved.** A restore that renumbers everything produces a library
  that looks right and compares unequal, and then you can never tell a good
  backup from a bad one. Keeping ids means a round trip is checkable by
  equality, which is what the test does.
- **Restore is replace-all, in one transaction.** A backup answers "put it back
  how it was", not "merge this in somehow". Half-restoring on an error would
  leave a library that is neither the old one nor the new one.
- **The format is versioned.** A file written today should be recognisably
  refusable by a future version that cannot read it, rather than half-imported.

Derived values are deliberately absent: `times_cooked` comes back from the log,
aisles from the rules. Exporting them would invite a restore that disagrees
with its own source data.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models

# Bumped when the shape changes in a way an older reader would misread.
FORMAT_VERSION = 1

# Order matters: parents before children, because restore inserts in this
# order and the foreign keys are real.
_TABLES: list[tuple[str, type]] = [
    ("recipes", models.Recipe),
    ("ingredients", models.Ingredient),
    ("steps", models.Step),
    ("alternates", models.Alternate),
    ("shopping_list_items", models.ShoppingListItem),
    ("meal_plan_entries", models.MealPlanEntry),
    ("recipe_drafts", models.RecipeDraft),
    ("meal_plan_drafts", models.MealPlanDraft),
    ("recipe_provenance", models.RecipeProvenance),
    ("cook_log", models.CookLog),
    ("pantry_items", models.PantryItem),
    ("aisle_rules", models.AisleRule),
]


def _plain(value: Any) -> Any:
    """JSON-safe, without losing precision.

    Decimals become strings rather than floats: 1/3 of a cup should survive a
    backup as the number it was, and a float does not promise that.
    """
    import datetime
    import enum
    import uuid

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def _row(obj: Any) -> dict[str, Any]:
    return {
        column.key: _plain(getattr(obj, column.key))
        for column in obj.__table__.columns
    }


def export_library(db: Session) -> dict[str, Any]:
    """Everything, as plain JSON-able data."""
    data: dict[str, Any] = {"format_version": FORMAT_VERSION}
    for name, model in _TABLES:
        data[name] = [_row(row) for row in db.execute(select(model)).scalars().all()]
    return data


class RestoreError(RuntimeError):
    """The file cannot be restored, and nothing has been changed."""


def restore_library(db: Session, data: dict[str, Any]) -> dict[str, int]:
    """Replace the library with the contents of a backup.

    Everything happens in one transaction: a restore that fails half way would
    leave a library that is neither the old one nor the new one, which is the
    worst of the available outcomes.
    """
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        # Refusing is the honest answer. Guessing at an unknown shape is how a
        # backup silently becomes a corruption.
        raise RestoreError(
            f"This backup is format version {version!r}; this CookVault reads version "
            f"{FORMAT_VERSION}."
        )

    unknown = set(data) - {"format_version"} - {name for name, _ in _TABLES}
    if unknown:
        raise RestoreError(f"Unrecognised sections in this backup: {', '.join(sorted(unknown))}.")

    counts: dict[str, int] = {}
    try:
        # Children before parents on the way out, parents before children on
        # the way in.
        for _, model in reversed(_TABLES):
            db.execute(model.__table__.delete())
        for name, model in _TABLES:
            rows = data.get(name) or []
            if not isinstance(rows, list):
                raise RestoreError(f"Section {name!r} should be a list.")
            if rows:
                db.execute(model.__table__.insert(), rows)
            counts[name] = len(rows)
        db.commit()
    except (SQLAlchemyError, RestoreError) as exc:
        # A malformed backup is the caller's problem, not a crash -- and the
        # rollback is what makes "nothing was changed" true rather than
        # merely likely. Without it the deletes above would be left pending
        # on a poisoned session.
        db.rollback()
        if isinstance(exc, RestoreError):
            raise
        raise RestoreError(f"This backup could not be restored: {type(exc).__name__}.") from exc

    return counts
