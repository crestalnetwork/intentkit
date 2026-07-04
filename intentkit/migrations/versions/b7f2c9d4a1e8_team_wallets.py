"""team wallets (idempotent)

Wallets move from agents to teams. Creates the ``team_wallets`` table,
back-fills one wallet row per agent that owned one (team = the agent's team,
falling back to the synthetic ``system`` team), binds each agent to its
migrated wallet via the new ``agents.wallet_id``, then drops the per-agent
wallet columns from ``agents``, ``templates`` and ``agent_data``.

Authored idempotently like the other post-baseline revisions: ``safe_migrate``
create-only sync may have already created ``team_wallets`` and
``agents.wallet_id`` from the models, and the back-fill skips agents whose
``wallet_id`` is already set, so re-running is always safe. On a fresh
database the legacy columns don't exist and the back-fill is skipped.
``agent_data.cdp_wallet_data`` is dropped without copying: it was a legacy
column from the CDP v1 SDK with no remaining reader (live CDP wallets are
custodied server-side and need only the address).

Revision ID: b7f2c9d4a1e8
Revises: 91c3a4b7e5d0
Create Date: 2026-07-05 00:00:00.000000

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from epyxid import XID

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "b7f2c9d4a1e8"
down_revision: Union[str, Sequence[str], None] = "91c3a4b7e5d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(insp: sa.Inspector, table: str) -> set[str]:
    return {col["name"] for col in insp.get_columns(table)}


def upgrade() -> None:
    """Upgrade schema (idempotent — safe whether or not objects already exist)."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. team_wallets table
    if not insp.has_table("team_wallets"):
        op.create_table(
            "team_wallets",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("team_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("wallet_provider", sa.String(), nullable=False),
            sa.Column("network_id", sa.String(), nullable=True),
            sa.Column("evm_wallet_address", sa.String(), nullable=True),
            sa.Column("solana_wallet_address", sa.String(), nullable=True),
            sa.Column("wallet_data", sa.String(), nullable=True),
            sa.Column("weekly_spending_limit", sa.Float(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_team_wallets_team ON team_wallets (team_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_team_wallets_team_name "
        "ON team_wallets (team_id, name)"
    )

    # 2. agents.wallet_id binding column
    op.execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS wallet_id VARCHAR")

    # 3. Back-fill from the legacy per-agent wallet columns (only when they
    # still exist — a fresh database created from the new models has none).
    agent_cols = _column_names(insp, "agents")
    agent_data_cols = (
        _column_names(insp, "agent_data") if insp.has_table("agent_data") else set()
    )
    if "wallet_provider" in agent_cols and "evm_wallet_address" in agent_data_cols:
        _backfill_team_wallets(bind)

    # 4. Drop the legacy per-agent wallet columns
    op.execute(
        "ALTER TABLE agents "
        "DROP COLUMN IF EXISTS wallet_provider, "
        "DROP COLUMN IF EXISTS readonly_wallet_address, "
        "DROP COLUMN IF EXISTS weekly_spending_limit"
    )
    op.execute("ALTER TABLE templates DROP COLUMN IF EXISTS wallet_provider")
    op.execute(
        "ALTER TABLE agent_data "
        "DROP COLUMN IF EXISTS evm_wallet_address, "
        "DROP COLUMN IF EXISTS solana_wallet_address, "
        "DROP COLUMN IF EXISTS cdp_wallet_data, "
        "DROP COLUMN IF EXISTS privy_wallet_data, "
        "DROP COLUMN IF EXISTS native_wallet_data"
    )


def _backfill_team_wallets(bind: sa.Connection) -> None:
    # Agents without a team fall back to the synthetic "system" team. There
    # are intentionally no FK constraints, and the API creates the system
    # user/team rows at startup, so no insert is needed here.
    rows = bind.execute(
        sa.text(
            """
            SELECT a.id, a.name, a.owner, a.team_id, a.network_id,
                   a.wallet_provider, a.readonly_wallet_address,
                   a.weekly_spending_limit,
                   d.evm_wallet_address, d.solana_wallet_address,
                   d.privy_wallet_data, d.native_wallet_data
            FROM agents a
            LEFT JOIN agent_data d ON d.id = a.id
            WHERE a.wallet_id IS NULL
              AND a.wallet_provider IS NOT NULL
              AND a.wallet_provider NOT IN ('none')
            """
        )
    ).all()

    migrated = 0
    for row in rows:
        provider = row.wallet_provider
        if provider in ("safe", "privy"):
            wallet_data = row.privy_wallet_data
        elif provider == "native":
            wallet_data = row.native_wallet_data
        else:
            wallet_data = None

        # Readonly agents may never have synced their watched address into
        # agent_data (it was copied lazily on first wallet access).
        evm_address = row.evm_wallet_address or row.readonly_wallet_address

        # An agent that never initialized its wallet has nothing to migrate.
        if not evm_address and not wallet_data:
            continue

        wallet_id = str(XID())
        team_id = row.team_id or "system"
        base_name = (row.name or "wallet").strip() or "wallet"
        # Suffix with the full agent id (an XID): globally unique, so two
        # same-named agents can never collide on the (team_id, name) index.
        name = f"{base_name[:40]}-{row.id}"

        bind.execute(
            sa.text(
                """
                INSERT INTO team_wallets (
                    id, team_id, name, wallet_provider, network_id,
                    evm_wallet_address, solana_wallet_address, wallet_data,
                    weekly_spending_limit, created_by
                ) VALUES (
                    :id, :team_id, :name, :provider, :network_id,
                    :evm, :solana, :wallet_data, :limit, :created_by
                )
                """
            ),
            {
                "id": wallet_id,
                "team_id": team_id,
                "name": name,
                "provider": provider,
                "network_id": row.network_id,
                "evm": evm_address,
                "solana": row.solana_wallet_address,
                "wallet_data": wallet_data,
                # The limit only ever applied to Safe wallets; legacy values
                # on other providers are stale noise.
                "limit": row.weekly_spending_limit if provider == "safe" else None,
                "created_by": row.owner or "system",
            },
        )
        bind.execute(
            sa.text("UPDATE agents SET wallet_id = :wid WHERE id = :aid"),
            {"wid": wallet_id, "aid": row.id},
        )
        migrated += 1

    logger.info("Migrated %s agent wallets to team_wallets", migrated)


def downgrade() -> None:
    """Re-add the per-agent columns.

    The back-filled data is NOT copied back; team_wallets is intentionally
    left in place so no wallet material is lost on downgrade.
    """
    op.execute(
        "ALTER TABLE agents "
        "ADD COLUMN IF NOT EXISTS wallet_provider VARCHAR, "
        "ADD COLUMN IF NOT EXISTS readonly_wallet_address VARCHAR, "
        "ADD COLUMN IF NOT EXISTS weekly_spending_limit FLOAT"
    )
    op.execute("ALTER TABLE templates ADD COLUMN IF NOT EXISTS wallet_provider VARCHAR")
    op.execute(
        "ALTER TABLE agent_data "
        "ADD COLUMN IF NOT EXISTS evm_wallet_address VARCHAR, "
        "ADD COLUMN IF NOT EXISTS solana_wallet_address VARCHAR, "
        "ADD COLUMN IF NOT EXISTS cdp_wallet_data VARCHAR, "
        "ADD COLUMN IF NOT EXISTS privy_wallet_data VARCHAR, "
        "ADD COLUMN IF NOT EXISTS native_wallet_data VARCHAR"
    )
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS wallet_id")
