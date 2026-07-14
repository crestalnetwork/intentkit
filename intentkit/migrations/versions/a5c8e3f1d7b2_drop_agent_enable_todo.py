"""drop agents/templates enable_todo (idempotent)

The todo list is always on now: every agent gets the write_todos tool and
TodoMiddleware in non-sub-agent runs, so the per-agent toggle is gone.
agent_drafts is skipped like in f2b8d5a3c9e7: the table only exists in the
baseline, has no ORM model, and is absent from freshly-migrated databases.

Revision ID: a5c8e3f1d7b2
Revises: f2b8d5a3c9e7
Create Date: 2026-07-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5c8e3f1d7b2"
down_revision: Union[str, Sequence[str], None] = "f2b8d5a3c9e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("agents", "templates")


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS enable_todo")


def downgrade() -> None:
    """Re-add the column (values are not recoverable; NULL means default off)."""
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS enable_todo BOOLEAN")
