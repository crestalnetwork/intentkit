"""team links (idempotent)

Schema delta for team links (external app accounts linked via Composio),
authored idempotently like the channel-centralization revision: ``safe_migrate``
may auto-create the table on deployments that run with DB_AUTO_MIGRATE, so
every op here is "create if missing". The unique index on
``connected_account_id`` is the important part — the OAuth completion callback
routes by that id, so one Composio account must never map to two teams.

Revision ID: 302f5420cd8f
Revises: 80d80453f3f0
Create Date: 2026-07-03 02:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "302f5420cd8f"
down_revision: Union[str, Sequence[str], None] = "80d80453f3f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (idempotent — safe whether or not objects already exist)."""
    insp = sa.inspect(op.get_bind())

    if not insp.has_table("team_links"):
        op.create_table(
            "team_links",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("team_id", sa.String(), nullable=False),
            sa.Column("app", sa.String(), nullable=False),
            sa.Column("connected_account_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("account_label", sa.String(), nullable=True),
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

    op.execute("CREATE INDEX IF NOT EXISTS ix_team_links_team ON team_links (team_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_team_links_connected_account "
        "ON team_links (connected_account_id)"
    )


def downgrade() -> None:
    """Reverse the team-links delta (best-effort, IF EXISTS)."""
    op.execute("DROP INDEX IF EXISTS ix_team_links_connected_account")
    op.execute("DROP INDEX IF EXISTS ix_team_links_team")
    op.execute("DROP TABLE IF EXISTS team_links")
