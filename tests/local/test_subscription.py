"""Tests for local subscription endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.team_feed import TeamSubscription


@pytest.mark.asyncio
async def test_list_subscriptions_uses_system_team():
    """List subscriptions should use team_id='system'."""
    import app.local.content as content_module

    mock_subs = [
        TeamSubscription(
            team_id="system",
            agent_id="public-blog-writer",
            subscribed_at=datetime.now(),
        ),
    ]

    with patch.object(
        content_module, "get_subscriptions", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_subs
        result = await content_module.list_subscriptions_endpoint()

    mock_get.assert_called_once_with("system")
    assert len(result) == 1
    assert result[0].agent_id == "public-blog-writer"


@pytest.mark.asyncio
async def test_subscribe_uses_system_team():
    """Subscribe should use team_id='system'."""
    import app.local.content as content_module

    mock_sub = TeamSubscription(
        team_id="system",
        agent_id="public-blog-writer",
        subscribed_at=datetime.now(),
    )

    with patch.object(
        content_module, "subscribe_agent", new_callable=AsyncMock
    ) as mock_subscribe:
        mock_subscribe.return_value = mock_sub
        result = await content_module.subscribe_endpoint(
            agent_id="public-blog-writer"
        )

    mock_subscribe.assert_called_once_with("system", "public-blog-writer")
    assert result.agent_id == "public-blog-writer"


@pytest.mark.asyncio
async def test_unsubscribe_uses_system_team():
    """Unsubscribe should use team_id='system'."""
    import app.local.content as content_module

    with patch.object(
        content_module, "unsubscribe_agent", new_callable=AsyncMock
    ) as mock_unsub:
        mock_unsub.return_value = None
        result = await content_module.unsubscribe_endpoint(
            agent_id="public-blog-writer"
        )

    mock_unsub.assert_called_once_with("system", "public-blog-writer")
    assert result.status_code == 204


@pytest.mark.asyncio
async def test_list_subscriptions_empty():
    """Empty subscription list."""
    import app.local.content as content_module

    with patch.object(
        content_module, "get_subscriptions", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = []
        result = await content_module.list_subscriptions_endpoint()

    assert result == []
