"""Tests for team push error handling (intentkit/core/team/push.py)."""

import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.team.push import (
    _LARK_BASE_URLS,
    WechatPushWindowClosedError,
    _lark_tenant_token,
    _lark_token_cache,
    _send_lark,
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


class TestLarkToken:
    @pytest.mark.asyncio
    async def test_token_is_cached_per_app(self):
        _lark_token_cache.clear()
        client = AsyncMock()
        client.post = AsyncMock(
            return_value=_resp(
                {"code": 0, "tenant_access_token": "t-abc", "expire": 7200}
            )
        )
        base = _LARK_BASE_URLS["feishu"]

        t1 = await _lark_tenant_token(client, base, "cli_x", "sec")
        t2 = await _lark_tenant_token(client, base, "cli_x", "sec")

        assert t1 == t2 == "t-abc"
        # Second call is served from cache — only one network fetch.
        assert client.post.await_count == 1

    @pytest.mark.asyncio
    async def test_send_lark_success_fetches_then_sends(self):
        _lark_token_cache.clear()
        client = AsyncMock()
        client.post = AsyncMock(
            side_effect=[
                _resp({"code": 0, "tenant_access_token": "t", "expire": 7200}),
                _resp({"code": 0}),
            ]
        )
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=None)
        with patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx):
            await _send_lark("cli_y", "sec", "feishu", "oc_1", "hi")
        assert client.post.await_count == 2

    @pytest.mark.asyncio
    async def test_send_lark_evicts_cached_token_on_api_error(self):
        _lark_token_cache.clear()
        # Warm cache so the message send (which errors) is the only call.
        _lark_token_cache["cli_x"] = ("t-old", time.monotonic() + 9999)
        client = AsyncMock()
        client.post = AsyncMock(return_value=_resp({"code": 230002, "msg": "bad"}))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=None)
        with patch(f"{MODULE_PUSH}.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(RuntimeError, match="Lark API error"):
                await _send_lark("cli_x", "sec", "feishu", "oc_1", "hi")
        # A failed send drops the (possibly stale) token so the next push refetches.
        assert "cli_x" not in _lark_token_cache


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
