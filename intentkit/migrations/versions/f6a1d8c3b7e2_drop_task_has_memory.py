"""drop autonomous_tasks.has_memory (idempotent)

Autonomous runs never retain conversation history between runs anymore —
every run starts from a clean thread, and tasks persist cross-run facts via
their cron-scoped memory (the memories table). The per-task retention toggle
is therefore gone.

Revision ID: f6a1d8c3b7e2
Revises: e3f8b2a9c5d1
Create Date: 2026-07-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a1d8c3b7e2"
down_revision: Union[str, Sequence[str], None] = "e3f8b2a9c5d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    op.execute("ALTER TABLE autonomous_tasks DROP COLUMN IF EXISTS has_memory")


def downgrade() -> None:
    """Re-add the column (old per-task settings are not recoverable)."""
    op.execute(
        "ALTER TABLE autonomous_tasks ADD COLUMN IF NOT EXISTS has_memory "
        "BOOLEAN NOT NULL DEFAULT false"
    )
