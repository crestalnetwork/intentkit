from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import intentkit.core.team.feed as feed_module
from intentkit.core.team.feed import (
    _build_cursor,
    _parse_cursor,
    fan_out_activity,
    fan_out_post,
    query_activity_feed,
    query_post_feed,
)
from intentkit.utils.error import IntentKitAPIError

# ---------------------------------------------------------------------------
# _parse_cursor
# ---------------------------------------------------------------------------


class TestParseCursor:
    def test_valid_cursor(self):
        dt = datetime(2026, 3, 26, 12, 0, 0)
        cursor = f"{dt.isoformat()}|item-123"
        parsed_dt, parsed_id = _parse_cursor(cursor)
        assert parsed_dt == dt
        assert parsed_id == "item-123"

    def test_missing_pipe_raises_400(self):
        with pytest.raises(IntentKitAPIError) as exc_info:
            _parse_cursor("no-pipe-here")
        assert exc_info.value.status_code == 400

    def test_invalid_datetime_raises_400(self):
        with pytest.raises(IntentKitAPIError) as exc_info:
            _parse_cursor("not-a-datetime|item-1")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# _build_cursor
# ---------------------------------------------------------------------------


class TestBuildCursor:
    def test_builds_correct_string(self):
        dt = datetime(2026, 1, 15, 8, 30, 0)
        result = _build_cursor(dt, "item-42")
        assert result == f"{dt.isoformat()}|item-42"


# ---------------------------------------------------------------------------
# Helpers for async DB mocking
# ---------------------------------------------------------------------------


def _mock_session_context(mock_session):
    """Wrap an AsyncMock session in a context-manager mock suitable for
    monkeypatching ``get_session``."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


def _scalars_result(rows):
    """Return a mock execute-result whose ``.scalars().all()`` yields *rows*."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


# ---------------------------------------------------------------------------
# fan_out_activity
# ---------------------------------------------------------------------------


class TestFanOutActivity:
    @pytest.mark.asyncio
    async def test_no_subscriptions_returns_early(self, monkeypatch):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        monkeypatch.setattr(
            feed_module, "get_session", lambda: _mock_session_context(mock_session)
        )

        await fan_out_activity("act-1", "agent-1", datetime.now())

        # Only the subscription query should have been executed
        assert mock_session.execute.await_count == 1
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_subscriptions_inserts(self, monkeypatch):
        mock_session = AsyncMock()
        # First call: subscription query returns team ids
        # Second call: insert statement
        mock_session.execute = AsyncMock(
            side_effect=[
                _scalars_result(["team-a", "team-b"]),
                MagicMock(),  # insert result
            ]
        )
        monkeypatch.setattr(
            feed_module, "get_session", lambda: _mock_session_context(mock_session)
        )

        await fan_out_activity("act-1", "agent-1", datetime(2026, 3, 26))

        assert mock_session.execute.await_count == 2
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# fan_out_post
# ---------------------------------------------------------------------------


class TestFanOutPost:
    @pytest.mark.asyncio
    async def test_no_subscriptions_returns_early(self, monkeypatch):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        monkeypatch.setattr(
            feed_module, "get_session", lambda: _mock_session_context(mock_session)
        )

        await fan_out_post("post-1", "agent-1", datetime.now())

        assert mock_session.execute.await_count == 1
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multiple_subscriptions_inserts(self, monkeypatch):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[
                _scalars_result(["team-x", "team-y", "team-z"]),
                MagicMock(),
            ]
        )
        monkeypatch.setattr(
            feed_module, "get_session", lambda: _mock_session_context(mock_session)
        )

        await fan_out_post("post-1", "agent-1", datetime(2026, 3, 26))

        assert mock_session.execute.await_count == 2
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# query_activity_feed
# ---------------------------------------------------------------------------


class TestQueryActivityFeed:
    @pytest.mark.asyncio
    async def test_empty_feed(self, monkeypatch):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        monkeypatch.setattr(
            feed_module, "get_session", lambda: _mock_session_context(mock_session)
        )

        items, next_cursor = await query_activity_feed("team-1", limit=20)

        assert items == []
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_returns_activities_with_next_cursor(self, monkeypatch):
        dt1 = datetime(2026, 3, 26, 10, 0, 0)
        dt2 = datetime(2026, 3, 26, 9, 0, 0)

        # Build fake feed rows (need activity_id and created_at attributes)
        feed_row_1 = MagicMock(activity_id="act-1", created_at=dt1)
        feed_row_2 = MagicMock(activity_id="act-2", created_at=dt2)
        # Return 2 rows for limit=1 so has_more is True
        feed_rows = [feed_row_1, feed_row_2]

        # Build fake activity table rows
        activity_row_1 = MagicMock()
        activity_row_1.id = "act-1"
        activity_row_1.agent_id = "agent-1"
        activity_row_1.agent_name = "Agent One"
        activity_row_1.agent_picture = None
        activity_row_1.text = "Hello"
        activity_row_1.images = []
        activity_row_1.video = None
        activity_row_1.post_id = None
        activity_row_1.created_at = dt1

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[
                _scalars_result(feed_rows),
                _scalars_result([activity_row_1]),
            ]
        )
        monkeypatch.setattr(
            feed_module, "get_session", lambda: _mock_session_context(mock_session)
        )

        # Patch AgentActivity.model_validate to avoid full Pydantic validation
        mock_activity = MagicMock()
        mock_activity.id = "act-1"
        monkeypatch.setattr(
            feed_module.AgentActivity,
            "model_validate",
            lambda row: mock_activity,
        )

        items, next_cursor = await query_activity_feed("team-1", limit=1)

        assert len(items) == 1
        assert next_cursor is not None
        assert "act-1" in next_cursor
        assert dt1.isoformat() in next_cursor


# ---------------------------------------------------------------------------
# query_post_feed
# ---------------------------------------------------------------------------


class TestQueryPostFeed:
    @pytest.mark.asyncio
    async def test_empty_feed(self, monkeypatch):
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=_scalars_result([]))
        monkeypatch.setattr(
            feed_module, "get_session", lambda: _mock_session_context(mock_session)
        )

        items, next_cursor = await query_post_feed("team-1", limit=20)

        assert items == []
        assert next_cursor is None
