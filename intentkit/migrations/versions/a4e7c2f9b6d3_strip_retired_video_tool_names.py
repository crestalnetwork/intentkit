"""strip retired video tool names from agents/templates tools (idempotent)

The Sora, Veo and Grok video tools were removed. Stored names for removed
tools are already ignored at bind time (get_tools skips unknown names), but
leaving them in the array makes them show up in tool pickers as entries that
can never resolve.

video_hailuo is deliberately NOT in the list — it kept its name across the
move to OpenRouter and the H3 model, so agents that enabled it keep it.

Revision ID: a4e7c2f9b6d3
Revises: c1d4b7e9a2f5
Create Date: 2026-08-23 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4e7c2f9b6d3"
down_revision: str | Sequence[str] | None = "c1d4b7e9a2f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAMES = ("video_sora", "video_sora_pro", "video_veo", "video_veo_fast", "video_grok")


def upgrade() -> None:
    """Remove the retired tool names from stored tools arrays (idempotent)."""
    removals = "".join(f" - '{name}'" for name in _NAMES)
    names_array = ", ".join(f"'{name}'" for name in _NAMES)
    for table in ("agents", "templates"):
        op.execute(
            f"UPDATE {table} SET tools = tools{removals} "
            f"WHERE tools IS NOT NULL "
            f"AND jsonb_exists_any(tools, ARRAY[{names_array}])"
        )


def downgrade() -> None:
    """No-op: the tools no longer exist, so restoring the names would only
    re-add entries that cannot resolve."""
