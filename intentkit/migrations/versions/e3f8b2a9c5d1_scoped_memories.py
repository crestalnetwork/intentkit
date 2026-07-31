"""scoped memories table + backfill from agent_data.long_term_memory (idempotent)

Long-term memory moves from the single ``agent_data.long_term_memory`` blob
to the ``memories`` table with one row per (agent, scope, scope_key). The
old blob was the agent's own memory, which in the new model is the owning
team's ``team``-scope memory:

- regular agents  -> scope='team', scope_key=agents.team_id (or 'system')
- lead agents     -> agent_data ids look like 'team-{team_id}' and have no
  agents row; scope_key is parsed from the id.

Revision ID: e3f8b2a9c5d1
Revises: d9a2e7c4f1b3
Create Date: 2026-07-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from epyxid import XID

# revision identifiers, used by Alembic.
revision: str = "e3f8b2a9c5d1"
down_revision: str | Sequence[str] | None = "d9a2e7c4f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id VARCHAR PRIMARY KEY,
            agent_id VARCHAR NOT NULL,
            scope VARCHAR NOT NULL,
            scope_key VARCHAR NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_memories_agent_scope_key
        ON memories (agent_id, scope, scope_key)
        """
    )

    bind = op.get_bind()

    # Backfill: only while the legacy column still exists (re-runs are no-ops).
    has_legacy_column = bind.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'agent_data'
              AND column_name = 'long_term_memory'
            """
        )
    ).scalar()

    if has_legacy_column:
        rows = bind.execute(
            sa.text(
                """
                SELECT d.id AS agent_id,
                       d.long_term_memory AS content,
                       a.team_id AS team_id,
                       (a.id IS NOT NULL) AS has_agent
                FROM agent_data d
                LEFT JOIN agents a ON a.id = d.id
                WHERE d.long_term_memory IS NOT NULL
                  AND d.long_term_memory <> ''
                """
            )
        ).fetchall()

        insert = sa.text(
            """
            INSERT INTO memories (id, agent_id, scope, scope_key, content)
            VALUES (:id, :agent_id, 'team', :scope_key, :content)
            ON CONFLICT (agent_id, scope, scope_key) DO NOTHING
            """
        )
        for row in rows:
            if row.has_agent:
                scope_key = row.team_id or "system"
            elif row.agent_id.startswith("team-"):
                # Lead agents have no agents row; their id embeds the team.
                scope_key = row.agent_id.removeprefix("team-")
            else:
                scope_key = "system"
            bind.execute(
                insert,
                {
                    "id": str(XID()),
                    "agent_id": row.agent_id,
                    "scope_key": scope_key,
                    "content": row.content,
                },
            )

    op.execute("ALTER TABLE agent_data DROP COLUMN IF EXISTS long_term_memory")


def downgrade() -> None:
    """Re-add the legacy column and restore team-scope rows into it."""
    op.execute(
        "ALTER TABLE agent_data ADD COLUMN IF NOT EXISTS long_term_memory VARCHAR"
    )
    # Restore only the OWNING team's row: public agents may hold one
    # team-scope row per visiting team.
    op.execute(
        """
        UPDATE agent_data d
        SET long_term_memory = m.content
        FROM memories m
        LEFT JOIN agents a ON a.id = m.agent_id
        WHERE m.agent_id = d.id
          AND m.scope = 'team'
          AND m.scope_key = CASE
                WHEN a.id IS NOT NULL THEN COALESCE(a.team_id, 'system')
                WHEN m.agent_id LIKE 'team-%' THEN substring(m.agent_id FROM 6)
                ELSE 'system'
              END
        """
    )
    op.execute("DROP TABLE IF EXISTS memories")
