"""Twitter OAuth2 token refresh functionality."""

import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from intentkit.config.db import get_session
from intentkit.models.agent_data import AgentData, AgentDataTable

from app.services.twitter.oauth2 import oauth2_user_handler

logger = logging.getLogger(__name__)


async def get_expiring_tokens(minutes_threshold: int = 10) -> Sequence[AgentDataTable]:
    """Get all agents with tokens expiring within the specified threshold.

    Args:
        minutes_threshold: Number of minutes before expiration to consider tokens as expiring

    Returns:
        List of AgentData records with expiring tokens
    """
    expiration_threshold = datetime.now(UTC) + timedelta(minutes=minutes_threshold)
    broken = datetime.now(UTC) - timedelta(days=1)

    async with get_session() as db:
        result = await db.execute(
            select(AgentDataTable).where(
                AgentDataTable.twitter_access_token.is_not(None),
                AgentDataTable.twitter_refresh_token.is_not(None),
                AgentDataTable.twitter_access_token_expires_at <= expiration_threshold,
                AgentDataTable.twitter_access_token_expires_at > broken,
            )
        )
    return result.scalars().all()


async def refresh_token(agent_data_record: AgentDataTable):
    """Refresh Twitter OAuth2 token for an agent.

    Args:
        agent_data_record: Agent data record containing refresh token
    """
    try:
        if not agent_data_record.twitter_refresh_token:
            return

        # Get new token using refresh token without blocking the event loop
        token = await asyncio.to_thread(
            oauth2_user_handler.refresh, agent_data_record.twitter_refresh_token
        )

        # Update token information
        update_data: dict[str, Any] = {
            "twitter_access_token": token.get("access_token"),
            "twitter_refresh_token": token.get("refresh_token"),
        }
        if "expires_at" in token:
            update_data["twitter_access_token_expires_at"] = datetime.fromtimestamp(
                token["expires_at"], UTC
            )

        _ = await AgentData.patch(agent_data_record.id, update_data)

        logger.info(
            f"Successfully refreshed Twitter token for agent {agent_data_record.id}, "
            f"expires at {agent_data_record.twitter_access_token_expires_at}"
        )
    except Exception as e:
        logger.error(
            f"Failed to refresh Twitter token for agent {agent_data_record.id}: {str(e)}"
        )


async def refresh_expiring_tokens():
    """Refresh all tokens that are about to expire.

    This function is designed to be called by the scheduler every minute.
    It will check for tokens expiring in the next 5 minutes and refresh them.
    """
    agents = await get_expiring_tokens()
    if not agents:
        return

    _ = await asyncio.gather(*(refresh_token(agent) for agent in agents))
