"""network follows wallet (idempotent)

Agents no longer carry a ``network_id``: on-chain tools take a
``wallet_address`` argument and operate on that wallet's network. The team
wallet column ``network_id`` is renamed to ``default_network_id`` to make its
role explicit, and the agent/template columns are dropped.

Revision ID: b2d7f4a9c8e3
Revises: a9c4e2f8b6d1
Create Date: 2026-07-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d7f4a9c8e3"
down_revision: Union[str, Sequence[str], None] = "a9c4e2f8b6d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS network_id")
    op.execute("ALTER TABLE agent_drafts DROP COLUMN IF EXISTS network_id")
    op.execute("ALTER TABLE templates DROP COLUMN IF EXISTS network_id")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'team_wallets' AND column_name = 'network_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'team_wallets'
                AND column_name = 'default_network_id'
            ) THEN
                ALTER TABLE team_wallets
                RENAME COLUMN network_id TO default_network_id;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Re-add the agent columns (values are not recoverable)."""
    op.execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS network_id VARCHAR")
    op.execute("ALTER TABLE agent_drafts ADD COLUMN IF NOT EXISTS network_id VARCHAR")
    op.execute("ALTER TABLE templates ADD COLUMN IF NOT EXISTS network_id VARCHAR")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'team_wallets'
                AND column_name = 'default_network_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'team_wallets' AND column_name = 'network_id'
            ) THEN
                ALTER TABLE team_wallets
                RENAME COLUMN default_network_id TO network_id;
            END IF;
        END $$;
        """
    )
