"""drop agent twitter columns (idempotent)

The per-agent Twitter/X binding (self-key tools and platform OAuth) has been
removed: agents no longer own social credentials — authorization is moving to
team-level (Composio team links). Drop the now-unused ``agent_data`` OAuth
columns and the ``agent_quotas`` twitter counters that only served the removed
twitter entrypoint/tools. Authored idempotently (``DROP COLUMN IF EXISTS``)
because deployments that run with DB_AUTO_MIGRATE use ``safe_migrate``
create-only sync and never re-add dropped columns, so re-running this is
always safe.

Revision ID: 91c3a4b7e5d0
Revises: 302f5420cd8f
Create Date: 2026-07-05 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "91c3a4b7e5d0"
down_revision: str | Sequence[str] | None = "302f5420cd8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (idempotent — safe whether or not columns still exist)."""
    op.execute(
        "ALTER TABLE agent_data "
        "DROP COLUMN IF EXISTS twitter_id, "
        "DROP COLUMN IF EXISTS twitter_username, "
        "DROP COLUMN IF EXISTS twitter_name, "
        "DROP COLUMN IF EXISTS twitter_access_token, "
        "DROP COLUMN IF EXISTS twitter_access_token_expires_at, "
        "DROP COLUMN IF EXISTS twitter_refresh_token, "
        "DROP COLUMN IF EXISTS twitter_self_key_refreshed_at, "
        "DROP COLUMN IF EXISTS twitter_is_verified"
    )
    op.execute(
        "ALTER TABLE agent_quotas "
        "DROP COLUMN IF EXISTS twitter_count_total, "
        "DROP COLUMN IF EXISTS twitter_limit_total, "
        "DROP COLUMN IF EXISTS twitter_count_monthly, "
        "DROP COLUMN IF EXISTS twitter_limit_monthly, "
        "DROP COLUMN IF EXISTS twitter_count_daily, "
        "DROP COLUMN IF EXISTS twitter_limit_daily, "
        "DROP COLUMN IF EXISTS last_twitter_time"
    )


def downgrade() -> None:
    """Re-add the columns (data is not recoverable)."""
    op.execute(
        "ALTER TABLE agent_data "
        "ADD COLUMN IF NOT EXISTS twitter_id VARCHAR, "
        "ADD COLUMN IF NOT EXISTS twitter_username VARCHAR, "
        "ADD COLUMN IF NOT EXISTS twitter_name VARCHAR, "
        "ADD COLUMN IF NOT EXISTS twitter_access_token VARCHAR, "
        "ADD COLUMN IF NOT EXISTS twitter_access_token_expires_at TIMESTAMPTZ, "
        "ADD COLUMN IF NOT EXISTS twitter_refresh_token VARCHAR, "
        "ADD COLUMN IF NOT EXISTS twitter_self_key_refreshed_at TIMESTAMPTZ, "
        "ADD COLUMN IF NOT EXISTS twitter_is_verified BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE agent_quotas "
        "ADD COLUMN IF NOT EXISTS twitter_count_total BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS twitter_limit_total BIGINT NOT NULL DEFAULT 99999999, "
        "ADD COLUMN IF NOT EXISTS twitter_count_monthly BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS twitter_limit_monthly BIGINT NOT NULL DEFAULT 99999999, "
        "ADD COLUMN IF NOT EXISTS twitter_count_daily BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS twitter_limit_daily BIGINT NOT NULL DEFAULT 99999999, "
        "ADD COLUMN IF NOT EXISTS last_twitter_time TIMESTAMPTZ"
    )
