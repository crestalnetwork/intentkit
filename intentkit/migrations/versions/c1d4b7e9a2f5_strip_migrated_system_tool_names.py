"""strip ui_show_card/ui_ask_user from agents/templates tools (idempotent)

These two names were migrated to auto-bound system tools
(intentkit/core/system_tools); legacy configs listing them in the tools
array were accepted-and-ignored via the MIGRATED_SYSTEM_TOOL_NAMES
tombstone. Stripping the stored names lets the tombstone be removed.

Revision ID: c1d4b7e9a2f5
Revises: d7a2f5c8b4e1
Create Date: 2026-07-21 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d4b7e9a2f5"
down_revision: str | Sequence[str] | None = "d7a2f5c8b4e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMES = ("ui_show_card", "ui_ask_user")


def upgrade() -> None:
    """Remove the migrated tool names from stored tools arrays (idempotent)."""
    for table in ("agents", "templates"):
        removals = "".join(f" - '{name}'" for name in _NAMES)
        names_array = ", ".join(f"'{name}'" for name in _NAMES)
        op.execute(
            f"UPDATE {table} SET tools = tools{removals} "
            f"WHERE tools IS NOT NULL "
            f"AND jsonb_exists_any(tools, ARRAY[{names_array}])"
        )


def downgrade() -> None:
    """No-op: the removed names carried no behavior (capability is auto-bound)."""
