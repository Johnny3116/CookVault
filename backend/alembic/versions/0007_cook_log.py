"""cooking history

What was actually cooked, and when. The questions this is for: what have I not
made in ages, what do I keep coming back to, and what did I think last time.

The rating and note sit on the occasion rather than on the recipe, because
"too salty" is a fact about the night you made it. Averaging those across
occasions is left to whoever wants it -- storing a single rating on the recipe
would throw away the thing that makes the history worth having.

No counters are added to `recipes`. `times_cooked` and `last_cooked_on` are
derived from this table at query time: a counter and a log can disagree, and
then something has to decide which one lied.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cook_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cooked_on", sa.Date, nullable=False),
        sa.Column("servings_made", sa.Integer, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # 1..5 enforced here rather than only in the API, so a stray write
        # cannot leave a 47 in the data for a reader to puzzle over later.
        sa.CheckConstraint("rating IS NULL OR (rating BETWEEN 1 AND 5)", name="ck_cook_log_rating"),
        sa.CheckConstraint(
            "servings_made IS NULL OR servings_made > 0", name="ck_cook_log_servings_made"
        ),
    )
    op.create_index("ix_cook_log_recipe_cooked_on", "cook_log", ["recipe_id", "cooked_on"])


def downgrade() -> None:
    op.drop_index("ix_cook_log_recipe_cooked_on", table_name="cook_log")
    op.drop_table("cook_log")
