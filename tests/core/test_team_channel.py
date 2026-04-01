"""Tests for intentkit.core.team.channel module."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from intentkit.core.team.channel import (
    _validate_channel_config,
    get_default_channel,
    get_team_channels,
    remove_team_channel,
    set_default_channel,
    set_team_channel,
)
from intentkit.models.team import TeamTable
from intentkit.models.team_channel import (
    TeamChannel,
    TeamChannelTable,
)

MODULE = "intentkit.core.team.channel"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session():
    """Return a mock async session usable as ``async with get_session() as db``."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, mock_session


def _make_channel_table_row(
    team_id="team1",
    channel_type="telegram",
    enabled=True,
    config=None,
    created_by="user1",
):
    row = MagicMock(spec=TeamChannelTable)
    row.team_id = team_id
    row.channel_type = channel_type
    row.enabled = enabled
    row.config = config
    row.created_by = created_by
    row.owner_id = None
    row.created_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    return row


# ---------------------------------------------------------------------------
# _validate_channel_config
# ---------------------------------------------------------------------------


class TestValidateChannelConfig:
    def test_valid_telegram_config(self):
        # Should not raise
        _validate_channel_config("telegram", {"token": "abc"})

    def test_invalid_telegram_config_missing_token(self):
        with pytest.raises(ValidationError):
            _validate_channel_config("telegram", {})

    def test_valid_wechat_config(self):
        _validate_channel_config(
            "wechat",
            {
                "bot_token": "tok",
                "baseurl": "https://example.com",
                "ilink_bot_id": "bot1",
                "user_id": "u1",
            },
        )

    def test_invalid_wechat_config_missing_fields(self):
        with pytest.raises(ValidationError):
            _validate_channel_config("wechat", {"bot_token": "tok"})

    def test_unknown_channel_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown channel type"):
            _validate_channel_config("slack", {"key": "val"})


# ---------------------------------------------------------------------------
# set_team_channel
# ---------------------------------------------------------------------------


class TestSetTeamChannel:
    @pytest.mark.asyncio
    async def test_creates_new_channel_and_auto_sets_default(self):
        ctx, mock_db = _make_mock_session()

        # db.get calls:
        # 1. TeamChannelTable -> None (new channel)
        # 2. TeamTable -> team with no default_channel
        # 3. TeamChannelDataTable -> None (no existing data row)
        mock_team = MagicMock(spec=TeamTable)
        mock_team.default_channel = None

        mock_db.get = AsyncMock(side_effect=[None, mock_team, None])

        expected_channel = TeamChannel(
            team_id="team1",
            channel_type="telegram",
            enabled=True,
            config={"token": "abc"},
            created_by="user1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with (
            patch(f"{MODULE}.get_session", return_value=ctx),
            patch.object(
                TeamChannel,
                "get",
                new_callable=AsyncMock,
                return_value=expected_channel,
            ),
        ):
            result = await set_team_channel(
                "team1", "telegram", {"token": "abc"}, "user1"
            )

        assert result.team_id == "team1"
        assert result.channel_type == "telegram"
        assert result.enabled is True
        # Team's default_channel should have been set
        assert mock_team.default_channel == "telegram"
        mock_db.add.assert_called()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_existing_channel(self):
        ctx, mock_db = _make_mock_session()

        existing_row = _make_channel_table_row(config={"token": "old"})
        # db.get calls:
        # 1. TeamChannelTable -> existing row (is_new=False, no TeamTable lookup)
        # 2. TeamChannelDataTable -> None (telegram data init)
        mock_db.get = AsyncMock(side_effect=[existing_row, None])

        expected_channel = TeamChannel(
            team_id="team1",
            channel_type="telegram",
            enabled=True,
            config={"token": "new"},
            created_by="user1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with (
            patch(f"{MODULE}.get_session", return_value=ctx),
            patch.object(
                TeamChannel,
                "get",
                new_callable=AsyncMock,
                return_value=expected_channel,
            ),
        ):
            result = await set_team_channel(
                "team1", "telegram", {"token": "new"}, "user1"
            )

        assert result.config == {"token": "new"}
        assert existing_row.config == {"token": "new"}
        assert existing_row.enabled is True
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# remove_team_channel
# ---------------------------------------------------------------------------


class TestRemoveTeamChannel:
    @pytest.mark.asyncio
    async def test_successful_removal(self):
        ctx, mock_db = _make_mock_session()

        with patch(f"{MODULE}.get_session", return_value=ctx):
            await remove_team_channel("team1", "telegram")

        # Two deletes: channel record + channel data
        assert mock_db.execute.await_count == 2
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_team_channels
# ---------------------------------------------------------------------------


class TestGetTeamChannels:
    @pytest.mark.asyncio
    async def test_returns_list_of_team_channel(self):
        ctx, mock_db = _make_mock_session()

        row1 = _make_channel_table_row(channel_type="telegram")
        row2 = _make_channel_table_row(channel_type="wechat")

        mock_scalars_result = MagicMock()
        mock_scalars_result.__iter__ = MagicMock(return_value=iter([row1, row2]))
        mock_db.scalars = AsyncMock(return_value=mock_scalars_result)

        with patch(f"{MODULE}.get_session", return_value=ctx):
            result = await get_team_channels("team1")

        assert len(result) == 2
        assert all(isinstance(ch, TeamChannel) for ch in result)
        assert result[0].channel_type == "telegram"
        assert result[1].channel_type == "wechat"


# ---------------------------------------------------------------------------
# set_default_channel
# ---------------------------------------------------------------------------


class TestSetDefaultChannel:
    @pytest.mark.asyncio
    async def test_channel_not_configured_raises(self):
        ctx, mock_db = _make_mock_session()
        # First db.get (TeamChannelTable) -> None
        mock_db.get = AsyncMock(return_value=None)

        with patch(f"{MODULE}.get_session", return_value=ctx):
            with pytest.raises(ValueError, match="not configured"):
                await set_default_channel("team1", "telegram")

    @pytest.mark.asyncio
    async def test_channel_disabled_raises(self):
        ctx, mock_db = _make_mock_session()
        disabled_channel = _make_channel_table_row(enabled=False)
        mock_db.get = AsyncMock(return_value=disabled_channel)

        with patch(f"{MODULE}.get_session", return_value=ctx):
            with pytest.raises(ValueError, match="not enabled"):
                await set_default_channel("team1", "telegram")

    @pytest.mark.asyncio
    async def test_team_not_found_raises(self):
        ctx, mock_db = _make_mock_session()
        channel_row = _make_channel_table_row(enabled=True)
        # First call returns channel, second call returns None (team not found)
        mock_db.get = AsyncMock(side_effect=[channel_row, None])

        with patch(f"{MODULE}.get_session", return_value=ctx):
            with pytest.raises(ValueError, match="not found"):
                await set_default_channel("team1", "telegram")

    @pytest.mark.asyncio
    async def test_successful_set(self):
        ctx, mock_db = _make_mock_session()
        channel_row = _make_channel_table_row(enabled=True)
        mock_team = MagicMock(spec=TeamTable)
        mock_team.default_channel = None
        mock_db.get = AsyncMock(side_effect=[channel_row, mock_team])

        with patch(f"{MODULE}.get_session", return_value=ctx):
            await set_default_channel("team1", "telegram")

        assert mock_team.default_channel == "telegram"
        mock_db.add.assert_called_with(mock_team)
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_default_channel
# ---------------------------------------------------------------------------


class TestGetDefaultChannel:
    @pytest.mark.asyncio
    async def test_team_not_found_returns_none(self):
        ctx, mock_db = _make_mock_session()
        mock_db.get = AsyncMock(return_value=None)

        with patch(f"{MODULE}.get_session", return_value=ctx):
            result = await get_default_channel("team1")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_default_channel(self):
        ctx, mock_db = _make_mock_session()
        mock_team = MagicMock(spec=TeamTable)
        mock_team.default_channel = "telegram"
        mock_db.get = AsyncMock(return_value=mock_team)

        with patch(f"{MODULE}.get_session", return_value=ctx):
            result = await get_default_channel("team1")

        assert result == "telegram"
