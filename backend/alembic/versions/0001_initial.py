"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-08

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

source_type = postgresql.ENUM("manual", "youtube", "tiktok", "instagram", "web", name="source_type")
ingredient_category = postgresql.ENUM(
    "raw_ingredient", "spice_sauce", "pantry_dry_good", "misc", name="ingredient_category"
)
alternate_type = postgresql.ENUM("cook_method", "ingredient_substitute", name="alternate_type")
meal_plan_mode = postgresql.ENUM("auto", "manual", name="meal_plan_mode")


def upgrade() -> None:
    # Note: op.create_table() below auto-creates each Enum type the first time
    # it's referenced as a column type -- no separate .create() call needed
    # (and calling both raises psycopg.errors.DuplicateObject).
    op.create_table(
        "recipes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_type", source_type, nullable=False, server_default="manual"),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("cook_methods", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("prep_time", sa.Integer(), nullable=True),
        sa.Column("cook_time", sa.Integer(), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("category", ingredient_category, nullable=False, server_default="misc"),
    )

    op.create_table(
        "steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column("temperature", sa.String(50), nullable=True),
        sa.Column("duration", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "alternates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", alternate_type, nullable=False),
        sa.Column("original_value", sa.String(255), nullable=False),
        sa.Column("alternate_value", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "shopping_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("category", ingredient_category, nullable=False, server_default="misc"),
        sa.Column("is_checked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "meal_plan_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", meal_plan_mode, nullable=False, server_default="manual"),
    )


def downgrade() -> None:
    op.drop_table("meal_plan_entries")
    op.drop_table("shopping_list_items")
    op.drop_table("alternates")
    op.drop_table("steps")
    op.drop_table("ingredients")
    op.drop_table("recipes")

    bind = op.get_bind()
    meal_plan_mode.drop(bind, checkfirst=True)
    alternate_type.drop(bind, checkfirst=True)
    ingredient_category.drop(bind, checkfirst=True)
    source_type.drop(bind, checkfirst=True)
