"""video_fetch: a recipe that arrived as speech

`import_method` exists to answer "how much should I trust these numbers", and a
transcript is a genuinely different answer from a fetched page. `url_fetch`
means a publisher typed the amounts into HTML. `video_fetch` means some of them
were said out loud and transcribed by a machine, which is the least reliable
source in the system -- and the reviewer should be able to see that on the row
rather than infer it from the source_type.

ALTER TYPE ... ADD VALUE cannot be used in the same transaction that adds it,
and Alembic wraps a migration in one, so this commits first. That makes the
step non-atomic: if something failed after the commit the type would carry a
value nothing uses, which is harmless and leaves no bad data. The downgrade is
the awkward direction -- Postgres cannot drop an enum value -- so it rebuilds
the type without it, which is why it refuses when rows still use it rather than
destroying them.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-22

"""
from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE cannot run inside the migration's transaction block.
    op.execute("COMMIT")
    op.execute("ALTER TYPE import_method ADD VALUE IF NOT EXISTS 'video_fetch'")


def downgrade() -> None:
    bind = op.get_bind()
    still_used = bind.exec_driver_sql(
        "SELECT count(*) FROM recipe_provenance WHERE import_method = 'video_fetch'"
    ).scalar_one()
    if still_used:
        # Refusing beats the alternatives: rewriting those rows to some other
        # method would be a lie about where the recipe came from, and deleting
        # them would take the recipes' provenance with them.
        raise RuntimeError(
            f"{still_used} provenance rows still use import_method='video_fetch'. "
            "Change or remove them before downgrading past 0011."
        )

    # Postgres has no DROP VALUE, so the type is rebuilt without it.
    op.execute("ALTER TYPE import_method RENAME TO import_method_old")
    op.execute(
        "CREATE TYPE import_method AS ENUM ('manual', 'paste', 'url_fetch', 'agent')"
    )
    op.execute(
        "ALTER TABLE recipe_provenance ALTER COLUMN import_method DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE recipe_provenance ALTER COLUMN import_method "
        "TYPE import_method USING import_method::text::import_method"
    )
    op.execute("DROP TYPE import_method_old")
