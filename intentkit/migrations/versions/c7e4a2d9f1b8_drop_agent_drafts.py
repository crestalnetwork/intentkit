"""drop agent_drafts (draft concept removed)

The draft flow is gone — agent changes are deployed directly, so the
agent_drafts staging table has no readers or writers left.

Revision ID: c7e4a2d9f1b8
Revises: b2d7f4a9c8e3
Create Date: 2026-07-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e4a2d9f1b8"
down_revision: Union[str, Sequence[str], None] = "b2d7f4a9c8e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (idempotent). Dropping the table drops its indexes too."""
    op.execute("DROP TABLE IF EXISTS agent_drafts")


def downgrade() -> None:
    """No-op: draft data is not recoverable and the feature is removed.

    The full table definition remains in the baseline revision d904723340f2
    for reference.
    """
    pass
