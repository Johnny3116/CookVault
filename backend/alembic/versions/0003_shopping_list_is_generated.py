"""mark shopping list items as generated or hand-added

Regenerating the list needs to replace what /generate produced while leaving
anything typed in by hand alone. recipe_id can't answer that question: once
duplicate ingredients are merged across recipes there is no single recipe to
point at, so a merged row would look hand-added.

Existing rows with a recipe_id were produced by the old /generate, so they are
backfilled as generated.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-21

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shopping_list_items",
        sa.Column("is_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE shopping_list_items SET is_generated = true WHERE recipe_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("shopping_list_items", "is_generated")
