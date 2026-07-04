"""channel centralization (idempotent)

The schema delta for the centralized Slack/Lark channel work, authored
idempotently (every op is "create if missing") so it is correct regardless of
exactly how much of this initiative an existing deployment already has — the old
``safe_migrate`` path may have auto-created the tables/columns but never the
indexes (especially the JSONB expression indexes). On a fresh database the
baseline does not create any of this, so this revision builds it; on existing
production (stamped at the baseline) it fills only what is missing.

Covers:
  - team_channels / team_channel_data / team_channel_chats tables
  - users.slack_id / users.lark_id columns + their indexes
  - the OAuth routing indexes: unique partial expression indexes mapping a Slack
    workspace / Lark tenant to at most one team (confused-deputy guard)

Revision ID: 80d80453f3f0
Revises: d904723340f2
Create Date: 2026-06-26 23:57:20.517425

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "80d80453f3f0"
down_revision: Union[str, Sequence[str], None] = "d904723340f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(insp, name: str) -> bool:
    return insp.has_table(name)


def _has_column(insp, table: str, column: str) -> bool:
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    """Upgrade schema (idempotent — safe whether or not objects already exist)."""
    insp = sa.inspect(op.get_bind())

    if not _has_table(insp, "team_channels"):
        op.create_table(
            "team_channels",
            sa.Column("team_id", sa.String(), nullable=False),
            sa.Column("channel_type", sa.String(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("owner_id", sa.String(), nullable=True),
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
            sa.PrimaryKeyConstraint("team_id", "channel_type"),
        )

    if not _has_table(insp, "team_channel_data"):
        op.create_table(
            "team_channel_data",
            sa.Column("team_id", sa.String(), nullable=False),
            sa.Column("channel_type", sa.String(), nullable=False),
            sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.PrimaryKeyConstraint("team_id", "channel_type"),
        )

    if not _has_table(insp, "team_channel_chats"):
        op.create_table(
            "team_channel_chats",
            sa.Column("channel_type", sa.String(), nullable=False),
            sa.Column("chat_id", sa.String(), nullable=False),
            sa.Column("team_id", sa.String(), nullable=False),
            sa.Column("chat_name", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("channel_type", "chat_id"),
        )

    # users channel-identity columns (the existing table predates this migration).
    if not _has_column(insp, "users", "slack_id"):
        op.add_column("users", sa.Column("slack_id", sa.String(), nullable=True))
    if not _has_column(insp, "users", "lark_id"):
        op.add_column("users", sa.Column("lark_id", sa.String(), nullable=True))

    # Indexes — CREATE INDEX IF NOT EXISTS (Postgres) keeps this idempotent. The
    # safe_migrate auto-migrator added columns but never their indexes, so these
    # are the real gap on existing deployments.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_team_channel_chats_team "
        "ON team_channel_chats (team_id, channel_type)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_slack_id ON users (slack_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_lark_id ON users (lark_id)")

    # OAuth routing indexes: UNIQUE so one Slack workspace / Lark tenant binds to
    # at most one team (a second install fails closed instead of hijacking).
    # create_all/autogenerate cannot express these JSONB expression indexes.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_team_channels_slack_workspace "
        "ON team_channels ((config ->> 'workspace_id')) "
        "WHERE channel_type = 'slack'"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_team_channels_lark_tenant "
        "ON team_channels ((config ->> 'tenant_key')) "
        "WHERE channel_type = 'lark'"
    )


def downgrade() -> None:
    """Reverse the channel-centralization delta (best-effort, IF EXISTS)."""
    op.execute("DROP INDEX IF EXISTS ix_team_channels_lark_tenant")
    op.execute("DROP INDEX IF EXISTS ix_team_channels_slack_workspace")
    op.execute("DROP INDEX IF EXISTS ix_users_lark_id")
    op.execute("DROP INDEX IF EXISTS ix_users_slack_id")
    op.execute("DROP INDEX IF EXISTS ix_team_channel_chats_team")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS lark_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS slack_id")
    op.execute("DROP TABLE IF EXISTS team_channel_chats")
    op.execute("DROP TABLE IF EXISTS team_channel_data")
    op.execute("DROP TABLE IF EXISTS team_channels")
