"""team_links: add level and user_id, re-level existing rows

Links used to be team-level only. Apps in the whitelist now carry a level:
team-level links stay shared by the whole team, user-level links belong to a
single member (``user_id``).

Existing rows are normalized to the whitelist's levels in the same step —
the feature predates any production use, so everything converges on the new
rules instead of carrying a legacy exception: rows of user-level apps become
user-level links owned by whoever initiated them (``created_by``), and any
row that can't be bound to a user is dropped.

Revision ID: a9c4e2f8b6d1
Revises: f6a1d8c3b7e2
Create Date: 2026-07-07 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c4e2f8b6d1"
down_revision: str | Sequence[str] | None = "f6a1d8c3b7e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The apps that are user-level in the whitelist at the time of this revision
# (frozen copy — the live catalog in intentkit/models/team_link.py may gain
# or re-level apps later; those changes need their own data migrations).
_USER_LEVEL_APPS = "('gmail', 'outlook', 'googlecalendar', 'linkedin')"


def upgrade() -> None:
    """Upgrade schema and normalize existing rows (idempotent)."""
    op.execute(
        "ALTER TABLE team_links ADD COLUMN IF NOT EXISTS level "
        "VARCHAR NOT NULL DEFAULT 'team'"
    )
    op.execute("ALTER TABLE team_links ADD COLUMN IF NOT EXISTS user_id VARCHAR")
    # Rows of user-level apps become user-level links owned by their
    # initiator...
    op.execute(
        "UPDATE team_links SET level = 'user', user_id = created_by "
        f"WHERE app IN {_USER_LEVEL_APPS} AND created_by <> ''"
    )
    # ...and any that can't be bound to a user (no initiator recorded) are
    # dropped rather than left behind as team-level oddities.
    op.execute(
        f"DELETE FROM team_links WHERE app IN {_USER_LEVEL_APPS} AND level = 'team'"
    )


def downgrade() -> None:
    """Drop the level columns (the re-leveling is not reversed)."""
    op.execute("ALTER TABLE team_links DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE team_links DROP COLUMN IF EXISTS level")
