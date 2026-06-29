"""Tests for team push error handling (intentkit/core/team/push.py)."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.config.config import config
from intentkit.core.team.push import (
    WechatPushWindowClosedError,
    _send_lark,
    _send_slack,
    _send_wechat,
    push_to_team,
)
from intentkit.models.team_channel import TeamChannel, TeamChannelData

MODULE_PUSH = "intentkit.core.team.push"


def _mock_httpx_client(response_json):
    """Build a patched httpx.AsyncClient whose post() returns response_json."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=response_json)

    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


def _send_wechat_args():
    return {
        "baseurl": "https://ilink.example.com",
        "bot_token": "token",
        "bot_id": "bot1",
        "to_user_id": "user1",
        "context_token": "ctx",
        "text": "hello",
    }


class TestSendWechat:
    @pytest.mark.asyncio
    async def test_window_closed_raises_specific_error(self):
        ctx = _mock_httpx_client({"ret": -2})
        with patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(WechatPushWindowClosedError):
                await _send_wechat(**_send_wechat_args())

    @pytest.mark.asyncio
    async def test_other_error_raises_runtime_error(self):
        ctx = _mock_httpx_client({"ret": -1, "errmsg": "auth failed"})
        with patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(RuntimeError, match="ret=-1") as exc_info:
                await _send_wechat(**_send_wechat_args())
        assert not isinstance(exc_info.value, WechatPushWindowClosedError)

    @pytest.mark.asyncio
    async def test_success_on_zero_or_missing_ret(self):
        for payload in ({}, {"ret": 0}):
            ctx = _mock_httpx_client(payload)
            with patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx):
                await _send_wechat(**_send_wechat_args())


def _resp(payload):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=payload)
    return r


class TestSlackPush:
    @staticmethod
    def _client(response_json):
        client = AsyncMock()
        client.post = AsyncMock(return_value=_resp(response_json))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return client, ctx

    @pytest.mark.asyncio
    async def test_send_slack_success(self):
        client, ctx = self._client({"ok": True})
        with patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx):
            await _send_slack("xoxb-tok", "C0ABC", "hello")
        assert client.post.await_count == 1
        # Bot token is sent as a bearer header; chat_id + text as JSON (no token
        # exchange, unlike Lark).
        _, kwargs = client.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer xoxb-tok"
        assert kwargs["json"] == {"channel": "C0ABC", "text": "hello"}

    @pytest.mark.asyncio
    async def test_send_slack_error_raises(self):
        _, ctx = self._client({"ok": False, "error": "channel_not_found"})
        with patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(RuntimeError, match="Slack API error"):
                await _send_slack("xoxb-tok", "C0ABC", "hello")


class TestLarkPush:
    """Lark push is routed to the Go webhook service (it owns the token chain)."""

    @staticmethod
    def _client(status_code):
        resp = MagicMock()
        resp.status_code = status_code
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return client, ctx

    @pytest.mark.asyncio
    async def test_returns_false_when_unconfigured(self):
        # No service URL / secret → push degrades gracefully (no raise).
        with (
            patch.object(config, "lark_service_url", None),
            patch.object(config, "lark_internal_secret", None),
        ):
            assert await _send_lark("tk", "oc_1", "hello") is False

    @pytest.mark.asyncio
    async def test_posts_to_go_service(self):
        client, ctx = self._client(200)
        with (
            patch.object(config, "lark_service_url", "http://lark:8084"),
            patch.object(config, "lark_internal_secret", "shh"),
            patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx),
        ):
            assert await _send_lark("tk", "oc_1", "hello") is True
        args, kwargs = client.post.call_args
        assert args[0] == "http://lark:8084/lark/push"
        assert kwargs["json"] == {
            "tenant_key": "tk",
            "chat_id": "oc_1",
            "text": "hello",
        }
        assert kwargs["headers"]["X-Internal-Secret"] == "shh"

    @pytest.mark.asyncio
    async def test_non_200_raises(self):
        _, ctx = self._client(502)
        with (
            patch.object(config, "lark_service_url", "http://lark:8084"),
            patch.object(config, "lark_internal_secret", "shh"),
            patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx),
        ):
            with pytest.raises(RuntimeError, match="Lark push failed"):
                await _send_lark("tk", "oc_1", "hello")


class TestPushToTeamWindowClosed:
    @pytest.mark.asyncio
    async def test_window_closed_logs_info_not_error(self, caplog):
        channel = MagicMock()
        channel.enabled = True
        channel.config = {
            "bot_token": "bt",
            "baseurl": "https://ilink.example.com",
            "ilink_bot_id": "bot1",
            "user_id": "user1",
        }
        channel_data = MagicMock()
        channel_data.data = {"context_token": "ctx"}

        with (
            patch(
                f"{MODULE_PUSH}.get_push_channel",
                AsyncMock(return_value=("wechat", "user1")),
            ),
            patch.object(TeamChannel, "get", AsyncMock(return_value=channel)),
            patch.object(TeamChannelData, "get", AsyncMock(return_value=channel_data)),
            patch(
                f"{MODULE_PUSH}._send_wechat",
                AsyncMock(side_effect=WechatPushWindowClosedError("ret=-2")),
            ),
            caplog.at_level(logging.INFO, logger=MODULE_PUSH),
        ):
            result = await push_to_team("team1", "hello")

        assert result is False
        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert not errors
        assert any("window closed" in r.getMessage() for r in caplog.records)
