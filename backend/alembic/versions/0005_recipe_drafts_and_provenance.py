"""recipe drafts and provenance

The staging area between "something proposed a recipe" and "the cookbook
contains a recipe". Nothing reaches `recipes` without passing validation and
then a human, and the path is the same whether a person typed the draft or a
model produced it.

Provenance keeps the raw source text and the extracted structure in separate
columns. Merged into one, "did the transcript say 2 tsp, or did the model
decide that?" becomes unanswerable, and that is the question worth asking.

`source_type` is the existing enum, reused rather than duplicated: where a
recipe came from means the same thing here. `import_method` is new, and says
how it arrived -- typed, pasted, fetched, or extracted by an agent. Only the
second one tells you how far to trust the numbers.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# create_type=False: `source_type` already exists (recipes use it), so let the
# column reference it rather than trying to create it a second time.
source_type = postgresql.ENUM(
    "manual", "youtube", "tiktok", "instagram", "web", name="source_type", create_type=False
)
# Same create_type=False for the new ones: they are created explicitly in
# upgrade() so that the enum exists before any table references it, and
# without this flag create_table would try to create each one a second time.
draft_status = postgresql.ENUM(
    "draft", "ready", "promoted", "discarded", name="draft_status", create_type=False
)
import_method = postgresql.ENUM(
    "manual", "paste", "url_fetch", "agent", name="import_method", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    draft_status.create(bind, checkfirst=True)
    import_method.create(bind, checkfirst=True)

    op.create_table(
        "recipe_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("status", draft_status, nullable=False, server_default="draft"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "promoted_recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # The drafts list is "what still needs my attention", i.e. filtered by
    # status and shown newest first.
    op.create_index("ix_recipe_drafts_status_updated", "recipe_drafts", ["status", "updated_at"])

    op.create_table(
        "recipe_provenance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipe_drafts.id", ondelete="CASCADE"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=True,
            unique=True,
        ),
        sa.Column("source_type", source_type, nullable=False, server_default="manual"),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("source_title", sa.String(512), nullable=True),
        sa.Column("import_method", import_method, nullable=False, server_default="manual"),
        sa.Column("original_text", sa.Text, nullable=True),
        sa.Column("extracted_payload", postgresql.JSONB, nullable=True),
        sa.Column("agent_model", sa.String(255), nullable=True),
        sa.Column("agent_version", sa.String(64), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Provenance of nothing is not provenance. After promotion a row
        # legitimately carries both, which is how the recipe keeps the history.
        sa.CheckConstraint(
            "draft_id IS NOT NULL OR recipe_id IS NOT NULL",
            name="ck_recipe_provenance_has_subject",
        ),
    )


def downgrade() -> None:
    op.drop_table("recipe_provenance")
    op.drop_index("ix_recipe_drafts_status_updated", table_name="recipe_drafts")
    op.drop_table("recipe_drafts")
    bind = op.get_bind()
    import_method.drop(bind, checkfirst=True)
    draft_status.drop(bind, checkfirst=True)
    # source_type is left alone on purpose: recipes still use it.
