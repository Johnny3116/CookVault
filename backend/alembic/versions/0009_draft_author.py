"""who put a draft in the queue, and what they wanted to say about it

`created_by` is recorded rather than inferred. Provenance already says where
content came from, but it is optional and it is a claim about the *source*;
this is a fact about the caller, established by which door the request arrived
through. It is what turns "the agent can't edit a draft John started" from an
intention into something the database can answer.

Existing rows backfill to `human`, which is true: everything in the queue
before this migration was created through the web UI or the import endpoints,
and the agent surface did not exist.

`note` is a message to the reviewer -- why this, and what the proposer was
unsure about. It stays on the draft and never becomes part of the recipe.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# create_type=False plus an explicit create(): op.add_column would otherwise
# try to create the type itself and collide with the one made here.
draft_author = postgresql.ENUM("human", "agent", name="draft_author", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    draft_author.create(bind, checkfirst=True)

    op.add_column(
        "recipe_drafts",
        sa.Column(
            "created_by",
            draft_author,
            nullable=False,
            # Everything already in the queue was put there by a human: this
            # column ships in the same release as the surface an agent could
            # use, so there is nothing else it could be.
            server_default="human",
        ),
    )
    # The default existed only to fill the rows that were already there. Left
    # in place it would be schema drift against the model, which declares the
    # default in Python -- and `alembic check` would be right to complain.
    op.alter_column("recipe_drafts", "created_by", server_default=None)

    op.add_column("recipe_drafts", sa.Column("note", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("recipe_drafts", "note")
    op.drop_column("recipe_drafts", "created_by")
    draft_author.drop(op.get_bind(), checkfirst=True)
