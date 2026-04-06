"""Team channel management functions."""

from __future__ import annotations

import logging
import random

from sqlalchemy import delete, select

from intentkit.config.db import get_session
from intentkit.models.team import TeamTable
from intentkit.models.team_channel import (
    TeamChannel,
    TeamChannelDataTable,
    TeamChannelTable,
    TelegramChannelConfig,
    WechatChannelConfig,
)

logger = logging.getLogger(__name__)


def _validate_channel_config(channel_type: str, config: dict[str, object]) -> None:
    """Validate config for the given channel type. Raises ValueError on failure."""
    if channel_type == "telegram":
        TelegramChannelConfig.model_validate(config)
    elif channel_type == "wechat":
        WechatChannelConfig.model_validate(config)
    else:
        raise ValueError(f"Unknown channel type: {channel_type}")


async def set_team_channel(
    team_id: str, channel_type: str, config: dict[str, object], created_by: str
) -> TeamChannel:
    """Create or update a team channel. Validates config per channel_type.

    If this is the first channel configured for the team,
    it will automatically become the default_channel.
    """
    _validate_channel_config(channel_type, config)

    async with get_session() as db:
        existing = await db.get(
            TeamChannelTable, {"team_id": team_id, "channel_type": channel_type}
        )
        is_new = existing is None
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

        # Auto-set default_channel if team doesn't have one yet
        if is_new:
            team = await db.get(TeamTable, team_id)
            if team and team.default_channel is None:
                team.default_channel = channel_type
                db.add(team)

        # For telegram, initialize channel data with a pending status and verification code
        if channel_type == "telegram":
            code = f"{random.randint(0, 9999):04d}"
            data_row = await db.get(
                TeamChannelDataTable,
                {"team_id": team_id, "channel_type": channel_type},
            )
            if data_row:
                if data_row.data is None:
                    data_row.data = {}
                data_row.data["status"] = "pending"
                data_row.data["verification_code"] = code
                db.add(data_row)
            else:
                data_row = TeamChannelDataTable(
                    team_id=team_id,
                    channel_type=channel_type,
                    data={
                        "status": "pending",
                        "verification_code": code,
                        "whitelist": [],
                    },
                )
                db.add(data_row)

        await db.commit()

    result = await TeamChannel.get(team_id, channel_type)
    if not result:
        raise RuntimeError("Failed to read back team channel after save")
    return result


async def remove_team_channel(team_id: str, channel_type: str) -> None:
    """Delete a team channel record and its associated runtime data."""
    async with get_session() as db:
        stmt = delete(TeamChannelTable).where(
            TeamChannelTable.team_id == team_id,
            TeamChannelTable.channel_type == channel_type,
        )
        await db.execute(stmt)
        # Also clean up runtime data (status, whitelist, etc.)
        stmt_data = delete(TeamChannelDataTable).where(
            TeamChannelDataTable.team_id == team_id,
            TeamChannelDataTable.channel_type == channel_type,
        )
        await db.execute(stmt_data)
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


async def _require_enabled_channel_and_team(db, team_id: str, channel_type: str):
    """Validate that the channel exists, is enabled, and the team exists.

    Returns the TeamTable row. Raises ValueError on failure.
    """
    channel = await db.get(
        TeamChannelTable, {"team_id": team_id, "channel_type": channel_type}
    )
    if not channel:
        raise ValueError(f"Channel '{channel_type}' is not configured for this team")
    if not channel.enabled:
        raise ValueError(f"Channel '{channel_type}' is not enabled for this team")

    team = await db.get(TeamTable, team_id)
    if not team:
        raise ValueError(f"Team '{team_id}' not found")
    return team


async def set_default_channel(team_id: str, channel_type: str) -> None:
    """Set the default notification channel for a team.

    Validates that the channel exists and is enabled for the team.
    """
    async with get_session() as db:
        team = await _require_enabled_channel_and_team(db, team_id, channel_type)
        team.default_channel = channel_type
        db.add(team)
        await db.commit()


async def get_default_channel(team_id: str) -> str | None:
    """Get the default notification channel for a team."""
    async with get_session() as db:
        team = await db.get(TeamTable, team_id)
        if not team:
            return None
        return team.default_channel


async def set_push_channel(team_id: str, channel_type: str, chat_id: str) -> None:
    """Set the push target for a team (channel_type + specific chat_id).

    Validates that the channel exists and is enabled.
    """
    async with get_session() as db:
        team = await _require_enabled_channel_and_team(db, team_id, channel_type)
        team.default_channel = channel_type
        team.default_channel_chat_id = chat_id
        db.add(team)
        await db.commit()


async def set_push_channel_if_empty(
    team_id: str, channel_type: str, chat_id: str
) -> bool:
    """Set the push target only if not already set. Returns True if set."""
    async with get_session() as db:
        team = await db.get(TeamTable, team_id)
        if not team:
            return False

        if team.default_channel_chat_id is not None:
            return False

        # Verify channel exists
        channel = await db.get(
            TeamChannelTable, {"team_id": team_id, "channel_type": channel_type}
        )
        if not channel or not channel.enabled:
            return False

        team.default_channel = channel_type
        team.default_channel_chat_id = chat_id
        db.add(team)
        await db.commit()
        return True


async def get_push_channel(team_id: str) -> tuple[str, str] | None:
    """Get the push target (channel_type, chat_id) or None if unset."""
    async with get_session() as db:
        team = await db.get(TeamTable, team_id)
        if not team or not team.default_channel or not team.default_channel_chat_id:
            return None
        return (team.default_channel, team.default_channel_chat_id)
