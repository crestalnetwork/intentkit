"""Tests for push channel management and activity push functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.team.channel import (
    get_push_channel,
    set_push_channel,
    set_push_channel_if_empty,
)
from intentkit.models.team import TeamTable
from intentkit.models.team_channel import TeamChannelTable

MODULE_CHANNEL = "intentkit.core.team.channel"
MODULE_ACTIVITY = "intentkit.core.agent_activity"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, mock_session


def _make_channel_row(enabled=True):
    row = MagicMock(spec=TeamChannelTable)
    row.enabled = enabled
    return row


def _make_team(default_channel=None, default_channel_chat_id=None):
    team = MagicMock(spec=TeamTable)
    team.default_channel = default_channel
    team.default_channel_chat_id = default_channel_chat_id
    return team


# ---------------------------------------------------------------------------
# set_push_channel
# ---------------------------------------------------------------------------


class TestSetPushChannel:
    @pytest.mark.asyncio
    async def test_channel_not_configured_raises(self):
        ctx, mock_db = _make_mock_session()
        mock_db.get = AsyncMock(return_value=None)

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            with pytest.raises(ValueError, match="not configured"):
                await set_push_channel("team1", "telegram", "123")

    @pytest.mark.asyncio
    async def test_channel_disabled_raises(self):
        ctx, mock_db = _make_mock_session()
        mock_db.get = AsyncMock(return_value=_make_channel_row(enabled=False))

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            with pytest.raises(ValueError, match="not enabled"):
                await set_push_channel("team1", "telegram", "123")

    @pytest.mark.asyncio
    async def test_team_not_found_raises(self):
        ctx, mock_db = _make_mock_session()
        channel_row = _make_channel_row(enabled=True)
        mock_db.get = AsyncMock(side_effect=[channel_row, None])

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            with pytest.raises(ValueError, match="not found"):
                await set_push_channel("team1", "telegram", "123")

    @pytest.mark.asyncio
    async def test_successful_set(self):
        ctx, mock_db = _make_mock_session()
        channel_row = _make_channel_row(enabled=True)
        mock_team = _make_team()
        mock_db.get = AsyncMock(side_effect=[channel_row, mock_team])

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            await set_push_channel("team1", "telegram", "123")

        assert mock_team.default_channel == "telegram"
        assert mock_team.default_channel_chat_id == "123"
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# set_push_channel_if_empty
# ---------------------------------------------------------------------------


class TestSetPushChannelIfEmpty:
    @pytest.mark.asyncio
    async def test_team_not_found_returns_false(self):
        ctx, mock_db = _make_mock_session()
        mock_db.get = AsyncMock(return_value=None)

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            result = await set_push_channel_if_empty("team1", "telegram", "123")

        assert result is False

    @pytest.mark.asyncio
    async def test_already_set_returns_false(self):
        ctx, mock_db = _make_mock_session()
        mock_team = _make_team(
            default_channel="telegram", default_channel_chat_id="existing"
        )
        mock_db.get = AsyncMock(return_value=mock_team)

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            result = await set_push_channel_if_empty("team1", "wechat", "456")

        assert result is False
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_channel_not_enabled_returns_false(self):
        ctx, mock_db = _make_mock_session()
        mock_team = _make_team()
        disabled_channel = _make_channel_row(enabled=False)
        mock_db.get = AsyncMock(side_effect=[mock_team, disabled_channel])

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            result = await set_push_channel_if_empty("team1", "telegram", "123")

        assert result is False

    @pytest.mark.asyncio
    async def test_successful_set_if_empty(self):
        ctx, mock_db = _make_mock_session()
        mock_team = _make_team()
        channel_row = _make_channel_row(enabled=True)
        mock_db.get = AsyncMock(side_effect=[mock_team, channel_row])

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            result = await set_push_channel_if_empty("team1", "telegram", "123")

        assert result is True
        assert mock_team.default_channel == "telegram"
        assert mock_team.default_channel_chat_id == "123"
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_push_channel
# ---------------------------------------------------------------------------


class TestGetPushChannel:
    @pytest.mark.asyncio
    async def test_team_not_found_returns_none(self):
        ctx, mock_db = _make_mock_session()
        mock_db.get = AsyncMock(return_value=None)

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            result = await get_push_channel("team1")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_channel_set_returns_none(self):
        ctx, mock_db = _make_mock_session()
        mock_team = _make_team()
        mock_db.get = AsyncMock(return_value=mock_team)

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            result = await get_push_channel("team1")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_push_channel(self):
        ctx, mock_db = _make_mock_session()
        mock_team = _make_team(
            default_channel="telegram", default_channel_chat_id="123"
        )
        mock_db.get = AsyncMock(return_value=mock_team)

        with patch(f"{MODULE_CHANNEL}.get_session", return_value=ctx):
            result = await get_push_channel("team1")

        assert result == ("telegram", "123")


# ---------------------------------------------------------------------------
# _format_activity_push
# ---------------------------------------------------------------------------


class TestFormatActivityPush:
    @pytest.mark.asyncio
    async def test_basic_format(self):
        from intentkit.core.agent_activity import _format_activity_push

        activity = MagicMock()
        activity.agent_name = "TestBot"
        activity.agent_id = "bot1"
        activity.text = "Hello world"
        activity.link = None
        activity.post_id = None

        result = await _format_activity_push(activity)
        assert result == "[TestBot] Hello world"

    @pytest.mark.asyncio
    async def test_with_link(self):
        from intentkit.core.agent_activity import _format_activity_push

        activity = MagicMock()
        activity.agent_name = "TestBot"
        activity.agent_id = "bot1"
        activity.text = "Check this out"
        activity.link = "https://example.com"
        activity.post_id = None

        result = await _format_activity_push(activity)
        assert result == "[TestBot] Check this out\nhttps://example.com"

    @pytest.mark.asyncio
    async def test_fallback_to_agent_id(self):
        from intentkit.core.agent_activity import _format_activity_push

        activity = MagicMock()
        activity.agent_name = None
        activity.agent_id = "bot1"
        activity.text = "Hello"
        activity.link = None
        activity.post_id = None

        result = await _format_activity_push(activity)
        assert result == "[bot1] Hello"

    @pytest.mark.asyncio
    async def test_with_post_id(self, monkeypatch):
        from datetime import datetime

        import intentkit.core.agent_activity as agent_activity_module
        from intentkit.config.config import config
        from intentkit.core.agent_activity import _format_activity_push
        from intentkit.models.share_link import ShareLink, ShareLinkTargetType

        async def fake_create_share_link(target_type, target_id, agent_id, **_kwargs):
            return ShareLink(
                id="sl-abc",
                target_type=target_type,
                target_id=target_id,
                agent_id=agent_id,
                expires_at=datetime.now(),
                created_at=datetime.now(),
            )

        monkeypatch.setattr(
            agent_activity_module, "create_share_link", fake_create_share_link
        )

        activity = MagicMock()
        activity.agent_name = "TestBot"
        activity.agent_id = "bot1"
        activity.text = "Hello"
        activity.link = None
        activity.post_id = "post123"

        result = await _format_activity_push(activity)
        assert result == f"[TestBot] Hello\n{config.app_base_url}/share/sl-abc"
        _ = ShareLinkTargetType  # keep import used
