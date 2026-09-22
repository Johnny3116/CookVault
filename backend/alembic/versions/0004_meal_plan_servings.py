"""plan servings and meal slot on meal plan entries

Scaling, planning and shopping generation are one pipeline: planning "risotto
for 8" has to buy for 8. The plan therefore needs to record the servings
wanted on the day.

Stored as target servings rather than a scale multiplier. "Make this for 8"
stays meaningful forever, while "scale = 2.0" silently becomes wrong the day
the recipe's own yield is corrected from 4 to 6.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

meal_type = postgresql.ENUM("breakfast", "lunch", "dinner", "snack", name="meal_type")


def upgrade() -> None:
    # add_column does not auto-create the enum the way create_table does.
    meal_type.create(op.get_bind(), checkfirst=True)
    op.add_column("meal_plan_entries", sa.Column("meal_type", meal_type, nullable=True))
    op.add_column("meal_plan_entries", sa.Column("servings", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("meal_plan_entries", "servings")
    op.drop_column("meal_plan_entries", "meal_type")
    meal_type.drop(op.get_bind(), checkfirst=True)
