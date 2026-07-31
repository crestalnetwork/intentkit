"""drop agents.wallet_id (idempotent)

Agents no longer reference a specific team wallet: web3 tools take a
``wallet_address`` argument and the agent chooses among ALL of its team's
wallets (listed in its system prompt). The binding column added by
``b7f2c9d4a1e8`` is therefore obsolete; the team_wallets rows it pointed at
remain the team's wallet pool.

Revision ID: d9a2e7c4f1b3
Revises: c4e8a1f6d2b9
Create Date: 2026-07-05 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9a2e7c4f1b3"
down_revision: str | Sequence[str] | None = "c4e8a1f6d2b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS wallet_id")


def downgrade() -> None:
    """Re-add the column (bindings are not recoverable)."""
    op.execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS wallet_id VARCHAR")
