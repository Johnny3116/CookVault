"""add ingredient display position

Ingredients were ordered by their UUID primary key, so the four-column layout
rendered them in arbitrary order and reshuffled after every edit. Backfill
existing rows by name so the initial order is at least stable and predictable.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingredients",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        UPDATE ingredients SET position = ordered.rn - 1
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY recipe_id ORDER BY name, id) AS rn
            FROM ingredients
        ) AS ordered
        WHERE ingredients.id = ordered.id
        """
    )
    op.create_index("ix_ingredients_recipe_position", "ingredients", ["recipe_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_ingredients_recipe_position", table_name="ingredients")
    op.drop_column("ingredients", "position")
