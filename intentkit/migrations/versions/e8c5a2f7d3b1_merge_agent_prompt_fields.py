"""merge agent prompt fields into system_prompt (idempotent)

``agents`` and ``templates`` merge the five prompt-shaping columns
(``purpose``, ``personality``, ``principles``, ``prompt``, ``prompt_append``)
into a single ``system_prompt`` TEXT column. The backfill reproduces what the
runtime prompt builder used to render from the separate fields: each non-empty
part is prefixed with its old level-2 heading (``## Purpose``,
``## Personality``, ``## Principles``, ``## Initial Rules`` for ``prompt``,
``## Additional Instructions`` for ``prompt_append``) and the parts are joined
with blank lines.

``agents.description`` (now a core field, the public display/routing text) is
additionally backfilled with a plain copy of ``purpose`` when unset: listings,
search, and the sub-agents prompt section used to fall back to ``purpose`` and
now read ``description`` only, so without this an agent that never set a
description would lose its display/routing text. ``purpose`` was already
exposed by the public API, so this leaks nothing new.

Idempotent: the backfills only touch rows where the target column is still
NULL/empty, and the old-column reads are guarded on column existence, so
re-running after the drops is safe.

Revision ID: e8c5a2f7d3b1
Revises: c7e4a2d9f1b8
Create Date: 2026-07-12 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8c5a2f7d3b1"
down_revision: str | Sequence[str] | None = "c7e4a2d9f1b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_COLUMNS = ("purpose", "personality", "principles", "prompt", "prompt_append")

_GUARD = """
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = '{table}' AND column_name = '{column}'
        ) THEN
"""


def _backfill_sql(table: str) -> str:
    """Backfill ``system_prompt`` from the old columns, guarded on existence.

    The UPDATE lives inside a plpgsql IF so this revision stays runnable after
    the old columns are dropped (statements in a false branch are never
    planned, so the dropped-column references do not error). The extra WHERE
    condition skips rows with nothing to merge — assigning NULL to them would
    still write new tuple versions.
    """
    guard = _GUARD.format(table=table, column="purpose")
    return f"""
    DO $$
    BEGIN
        {guard}
            UPDATE {table} SET system_prompt = concat_ws(E'\\n\\n',
                CASE WHEN purpose IS NOT NULL AND purpose <> ''
                    THEN E'## Purpose\\n\\n' || purpose END,
                CASE WHEN personality IS NOT NULL AND personality <> ''
                    THEN E'## Personality\\n\\n' || personality END,
                CASE WHEN principles IS NOT NULL AND principles <> ''
                    THEN E'## Principles\\n\\n' || principles END,
                CASE WHEN prompt IS NOT NULL AND prompt <> ''
                    THEN E'## Initial Rules\\n\\n' || prompt END,
                CASE WHEN prompt_append IS NOT NULL AND prompt_append <> ''
                    THEN E'## Additional Instructions\\n\\n' || prompt_append END
            )
            WHERE system_prompt IS NULL
              AND (coalesce(purpose, '') <> ''
                OR coalesce(personality, '') <> ''
                OR coalesce(principles, '') <> ''
                OR coalesce(prompt, '') <> ''
                OR coalesce(prompt_append, '') <> '');
        END IF;
    END $$;
    """


def _backfill_description_sql() -> str:
    """Backfill ``agents.description`` from ``purpose`` where unset."""
    guard = _GUARD.format(table="agents", column="purpose")
    return f"""
    DO $$
    BEGIN
        {guard}
            UPDATE agents SET description = purpose
            WHERE coalesce(description, '') = ''
              AND coalesce(purpose, '') <> '';
        END IF;
    END $$;
    """


def upgrade() -> None:
    """Upgrade schema (idempotent — safe whether or not columns still exist)."""
    op.execute(_backfill_description_sql())
    for table in ("agents", "templates"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS system_prompt TEXT")
        op.execute(_backfill_sql(table))
        drops = ", ".join(f"DROP COLUMN IF EXISTS {col}" for col in _OLD_COLUMNS)
        op.execute(f"ALTER TABLE {table} {drops}")


def downgrade() -> None:
    """Re-add the old columns; the merged text goes back into ``prompt``.

    The original per-field split is not recoverable — best effort restores the
    whole merged prompt as ``prompt`` so no content is lost. The description
    backfill is left in place (it is plain public text either way).
    """
    for table in ("agents", "templates"):
        adds = ", ".join(
            f"ADD COLUMN IF NOT EXISTS {col} VARCHAR" for col in _OLD_COLUMNS
        )
        op.execute(f"ALTER TABLE {table} {adds}")
        guard = _GUARD.format(table=table, column="system_prompt")
        op.execute(
            f"""
            DO $$
            BEGIN
                {guard}
                    UPDATE {table} SET prompt = system_prompt
                    WHERE prompt IS NULL AND system_prompt IS NOT NULL;
                END IF;
            END $$;
            """
        )
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS system_prompt")
