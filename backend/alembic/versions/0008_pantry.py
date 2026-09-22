"""pantry: things you keep in

Deliberately a name and a note. No quantities, no expiry dates, no lots --
tracking how much olive oil is left turns a cookbook into inventory software,
and the person who has to keep that accurate is the same person who wanted to
cook dinner.

Its one job is to flag a shopping line as "you probably already have this". It
never removes anything from a list: silently under-buying is worse than buying
a second jar of cumin.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pantry_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pantry_items_name", "pantry_items", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_pantry_items_name", table_name="pantry_items")
    op.drop_table("pantry_items")
