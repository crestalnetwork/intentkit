"""drop agents/templates super_mode and enable_long_term_memory (idempotent)

Super mode is gone: the default recursion limit is now the former super
value, so the per-agent escape hatch is meaningless. Long-term memory is
always on: memory belongs to the conversation scopes (team / user /
channel / cron), not to the agent, so there is nothing to toggle per agent.

Revision ID: a7d3e9f2c1b4
Revises: e8c5a2f7d3b1
Create Date: 2026-07-12 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d3e9f2c1b4"
down_revision: str | Sequence[str] | None = "e8c5a2f7d3b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    for table in ("agents", "templates"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS super_mode")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS enable_long_term_memory")


def downgrade() -> None:
    """Re-add the columns (values are not recoverable)."""
    for table in ("agents", "templates"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS super_mode BOOLEAN")
        op.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS enable_long_term_memory BOOLEAN"
        )
