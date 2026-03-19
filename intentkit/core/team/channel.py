"""Team channel management functions."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select

from intentkit.config.db import get_session
from intentkit.models.team_channel import (
    TeamChannel,
    TeamChannelTable,
    TelegramChannelConfig,
)

logger = logging.getLogger(__name__)


def _validate_channel_config(channel_type: str, config: dict[str, object]) -> None:
    """Validate config for the given channel type. Raises ValueError on failure."""
    if channel_type == "telegram":
        TelegramChannelConfig.model_validate(config)
    else:
        raise ValueError(f"Unknown channel type: {channel_type}")


async def set_team_channel(
    team_id: str, channel_type: str, config: dict[str, object], created_by: str
) -> TeamChannel:
    """Create or update a team channel. Validates config per channel_type."""
    _validate_channel_config(channel_type, config)

    async with get_session() as db:
        existing = await db.get(
            TeamChannelTable, {"team_id": team_id, "channel_type": channel_type}
        )
        if existing:
            existing.config = config
            existing.enabled = True
            db.add(existing)
        else:
            record = TeamChannelTable(
                team_id=team_id,
                channel_type=channel_type,
                enabled=True,
                config=config,
                created_by=created_by,
            )
            db.add(record)
        await db.commit()

    result = await TeamChannel.get(team_id, channel_type)
    if not result:
        raise RuntimeError("Failed to read back team channel after save")
    return result


async def remove_team_channel(team_id: str, channel_type: str) -> None:
    """Delete a team channel record."""
    async with get_session() as db:
        stmt = delete(TeamChannelTable).where(
            TeamChannelTable.team_id == team_id,
            TeamChannelTable.channel_type == channel_type,
        )
        await db.execute(stmt)
        await db.commit()


async def get_team_channel(team_id: str, channel_type: str) -> TeamChannel | None:
    """Get a specific team channel."""
    return await TeamChannel.get(team_id, channel_type)


async def get_team_channels(team_id: str) -> list[TeamChannel]:
    """Get all channels for a team."""
    async with get_session() as db:
        stmt = select(TeamChannelTable).where(TeamChannelTable.team_id == team_id)
        result = await db.scalars(stmt)
        return [TeamChannel.model_validate(row) for row in result]
