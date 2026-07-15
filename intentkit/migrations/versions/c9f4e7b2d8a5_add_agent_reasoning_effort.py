"""add agents/templates reasoning_effort (idempotent)

Reasoning/thinking effort becomes an agent-level setting on OpenRouter's
unified scale (none/minimal/low/medium/high/xhigh/max). NULL follows the
selected model's catalog default; values are clamped per model at request
time, so no backfill is needed. Agents on retired legacy ids simply inherit
their successor model's defaults.

Revision ID: c9f4e7b2d8a5
Revises: a5c8e3f1d7b2
Create Date: 2026-07-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f4e7b2d8a5"
down_revision: Union[str, Sequence[str], None] = "a5c8e3f1d7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    for table in ("agents", "templates"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS reasoning_effort VARCHAR"
        )


def downgrade() -> None:
    """Drop the columns."""
    for table in ("agents", "templates"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS reasoning_effort")
