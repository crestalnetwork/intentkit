"""drop agents.deployed_at (draft-era leftover)

The draft system is long gone — every create/update applies directly, so
"deploy" is no longer a distinct step. agents.deployed_at is replaced by the
auto-maintained updated_at as the executor-cache rebuild criterion (what it
was before drafts existed). The agent_drafts table itself was already dropped
by c7e4a2d9f1b8.

Idempotent: IF EXISTS, so databases created by safe_migrate upgrade cleanly.

Revision ID: d7a2f5c8b4e1
Revises: c9f4e7b2d8a5
Create Date: 2026-07-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a2f5c8b4e1"
down_revision: str | Sequence[str] | None = "c9f4e7b2d8a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS deployed_at")


def downgrade() -> None:
    """Re-add the column (values are not recoverable)."""
    op.execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS deployed_at TIMESTAMPTZ")
