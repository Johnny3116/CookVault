"""a proposed week, waiting to be said yes to

The same shape as a recipe draft, for the same reason: a plan somebody or
something produced is a proposal, and proposals go in a queue. Approving one is
what creates the real `meal_plan_entries` rows, and it is the only way an entry
is ever recorded as `auto` -- which is what finally makes that flag mean
something rather than being a value anyone could set.

The meals are JSONB, not child rows with foreign keys. A proposal is allowed to
be wrong: it can name a recipe that gets deleted before anyone looks at it, and
a real FK would quietly remove a line from the middle of a plan when that
happened. As data the gap stays visible and is reported at approval time, which
is when it matters.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# Both types already exist -- draft_status from 0005, draft_author from 0009 --
# so create_type=False stops create_table from trying to make them again.
draft_status = postgresql.ENUM(
    "draft", "ready", "promoted", "discarded", name="draft_status", create_type=False
)
draft_author = postgresql.ENUM("human", "agent", name="draft_author", create_type=False)


def upgrade() -> None:
    op.create_table(
        "meal_plan_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("status", draft_status, nullable=False, server_default="draft"),
        sa.Column("created_by", draft_author, nullable=False, server_default="human"),
        sa.Column("meals", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("agent_model", sa.String(255), nullable=True),
        sa.Column("agent_version", sa.String(64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # The defaults exist so the columns can be NOT NULL on a table that starts
    # empty; the model declares them in Python, so leaving them in the schema
    # would be drift `alembic check` is right to complain about.
    op.alter_column("meal_plan_drafts", "status", server_default=None)
    op.alter_column("meal_plan_drafts", "created_by", server_default=None)
    op.alter_column("meal_plan_drafts", "meals", server_default=None)

    op.create_index(
        "ix_meal_plan_drafts_status_updated", "meal_plan_drafts", ["status", "updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_meal_plan_drafts_status_updated", table_name="meal_plan_drafts")
    op.drop_table("meal_plan_drafts")
    # draft_status and draft_author are not dropped: they belong to 0005 and
    # 0009, which own their lifecycle. Dropping a type this table merely used
    # would take recipe_drafts down with it.
