"""drop agents/templates temperature, frequency_penalty, presence_penalty (idempotent)

Sampling parameters are removed from the system: current-generation models
either reject them (Claude 5 / GPT-5.6 / Kimi K2.x), silently ignore them
(DeepSeek V4 penalties, thinking-mode models), or recommend defaults
(Gemini 3.x). Every provider now runs with its own recommended defaults.

Revision ID: f2b8d5a3c9e7
Revises: a7d3e9f2c1b4
Create Date: 2026-07-14 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b8d5a3c9e7"
down_revision: str | Sequence[str] | None = "a7d3e9f2c1b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("temperature", "frequency_penalty", "presence_penalty")


def upgrade() -> None:
    """Upgrade schema (idempotent); one statement per table to take its lock once."""
    for table in ("agents", "templates"):
        drops = ", ".join(f"DROP COLUMN IF EXISTS {column}" for column in _COLUMNS)
        op.execute(f"ALTER TABLE {table} {drops}")


def downgrade() -> None:
    """Re-add the columns (values are not recoverable)."""
    for table in ("agents", "templates"):
        adds = ", ".join(
            f"ADD COLUMN IF NOT EXISTS {column} FLOAT" for column in _COLUMNS
        )
        op.execute(f"ALTER TABLE {table} {adds}")
