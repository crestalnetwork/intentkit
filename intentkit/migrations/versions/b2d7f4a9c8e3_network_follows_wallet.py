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
    """Upgrade schema (idempotent).

    Guard every DROP on the table's existence. Some environments were onboarded
    to Alembic by stamping the baseline without physically creating every
    baseline table (e.g. ``agent_drafts``). ``DROP COLUMN IF EXISTS`` only
    guards the column, not the table, so a bare ``ALTER TABLE`` on a missing
    table would raise ``UndefinedTable`` and abort the whole migration.
    """
    op.execute(
        """
        DO $$
        DECLARE
            t text;
        BEGIN
            FOREACH t IN ARRAY ARRAY['agents', 'agent_drafts', 'templates'] LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = t
                ) THEN
                    EXECUTE format(
                        'ALTER TABLE %I DROP COLUMN IF EXISTS network_id', t
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
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
    """Re-add the agent columns (values are not recoverable).

    Guarded on table existence for the same reason as ``upgrade``.
    """
    op.execute(
        """
        DO $$
        DECLARE
            t text;
        BEGIN
            FOREACH t IN ARRAY ARRAY['agents', 'agent_drafts', 'templates'] LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = t
                ) THEN
                    EXECUTE format(
                        'ALTER TABLE %I ADD COLUMN IF NOT EXISTS network_id VARCHAR', t
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
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
