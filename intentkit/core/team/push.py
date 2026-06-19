"""Team channel push functions.

Send proactive messages to a team's default push channel (Telegram or WeChat)
and record them in the chat message system.
"""

import base64
import json
import logging
import random
import time

import httpx
from epyxid import XID

from intentkit.config.config import config
from intentkit.core.team.channel import build_channel_chat_id, get_push_channel
from intentkit.models.chat import AuthorType
from intentkit.models.team_channel import (
    LarkChannelConfig,
    TeamChannel,
    TeamChannelData,
    TelegramChannelConfig,
    WechatChannelConfig,
    WechatChannelData,
)

logger = logging.getLogger(__name__)

# iLink message type/state constants (mirrors Go ilink/types.go)
_ILINK_MESSAGE_TYPE_BOT = 2
_ILINK_MESSAGE_STATE_FINISH = 2
_ILINK_ITEM_TYPE_TEXT = 1

# iLink returns ret=-2 when the session window is closed (the user hasn't
# messaged recently), so the bot has no permission to push. Expected condition,
# not an error worth alerting on.
_ILINK_RET_WINDOW_CLOSED = -2


class WechatPushWindowClosedError(RuntimeError):
    """Push rejected because the WeChat session window is closed (ret=-2)."""


def _rewrite_for_wechat(text: str) -> str:
    """Swap APP_BASE_URL for WECHAT_BASE_URL in WeChat-bound text."""
    if config.wechat_base_url:
        # Normalize trailing slashes on both sides so a misconfigured env var
        # like "https://cdn.example.com/" doesn't produce "...com//share/..."
        return text.replace(
            config.app_base_url.rstrip("/"),
            config.wechat_base_url.rstrip("/"),
        )
    return text


async def _send_telegram(token: str, chat_id: str, text: str) -> None:
    """Send a text message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={"chat_id": chat_id, "text": text})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data.get('description')}")


def _generate_wechat_uin() -> str:
    """Generate a random X-WECHAT-UIN header value (same as Go's generateWechatUIN)."""
    n = random.getrandbits(32)
    return base64.b64encode(str(n).encode()).decode()


async def _send_wechat(
    baseurl: str,
    bot_token: str,
    bot_id: str,
    to_user_id: str,
    context_token: str,
    text: str,
) -> None:
    """Send a text message via iLink Bot API."""
    body = {
        "msg": {
            "from_user_id": bot_id,
            "to_user_id": to_user_id,
            "client_id": str(XID()),
            "message_type": _ILINK_MESSAGE_TYPE_BOT,
            "message_state": _ILINK_MESSAGE_STATE_FINISH,
            "context_token": context_token,
            "item_list": [
                {"type": _ILINK_ITEM_TYPE_TEXT, "text_item": {"text": text}},
            ],
        },
        "base_info": {},
    }
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {bot_token}",
        "X-WECHAT-UIN": _generate_wechat_uin(),
    }
    async with httpx.AsyncClient(timeout=40) as client:
        resp = await client.post(
            f"{baseurl}/ilink/bot/sendmessage", json=body, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        logger.debug("iLink sendmessage response: %s", data)
        # iLink only includes `ret` on failure; a missing or zero ret means success
        # (matches the Go integration, which relies on int's zero-value default).
        ret = data.get("ret", 0)
        if ret == _ILINK_RET_WINDOW_CLOSED:
            raise WechatPushWindowClosedError(
                f"iLink push rejected: session window closed (ret={ret})"
            )
        if ret != 0:
            raise RuntimeError(
                f"iLink API error: ret={ret} errmsg={data.get('errmsg')}"
            )


# Open-platform hosts for the two Lark/Feishu environments. Keep in sync with
# the Go integration's larkclient.ResolveBaseURL, which mirrors them for inbound.
_LARK_BASE_URLS = {
    "feishu": "https://open.feishu.cn",
    "lark": "https://open.larksuite.com",
}

# Cache of tenant_access_tokens keyed by app_id. Lark tokens are valid ~2h and
# their generation is rate-limited, so reusing them across pushes matters (the
# Go bot path relies on the SDK's own cache for the same reason). A benign race
# — two coroutines refreshing at once — just costs one extra fetch.
_lark_token_cache: dict[str, tuple[str, float]] = {}
# Refresh a little before the real expiry so we never present a just-expired token.
_LARK_TOKEN_EXPIRY_SKEW = 300.0  # seconds


async def _lark_tenant_token(
    client: httpx.AsyncClient, base_url: str, app_id: str, app_secret: str
) -> str:
    """Return a (possibly cached) tenant_access_token for the app."""
    cached = _lark_token_cache.get(app_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]

    resp = await client.post(
        f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(
            f"Lark token error: code={data.get('code')} msg={data.get('msg')}"
        )
    token = data["tenant_access_token"]
    expire = float(data.get("expire", 7200))
    _lark_token_cache[app_id] = (
        token,
        time.monotonic() + max(0.0, expire - _LARK_TOKEN_EXPIRY_SKEW),
    )
    return token


async def _send_lark(
    app_id: str,
    app_secret: str,
    domain: str,
    chat_id: str,
    text: str,
) -> None:
    """Send a text message via the Lark/Feishu Bot API.

    Uses a cached tenant_access_token (exchanged from the app credentials), then
    posts a text message to the target chat. ``domain`` selects the Feishu
    (China) or Lark (international) open-platform host.
    """
    base_url = _LARK_BASE_URLS.get(domain, _LARK_BASE_URLS["feishu"])
    async with httpx.AsyncClient(timeout=30) as client:
        token = await _lark_tenant_token(client, base_url, app_id, app_secret)
        msg_resp = await client.post(
            f"{base_url}/open-apis/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
        )
        msg_resp.raise_for_status()
        msg_data = msg_resp.json()
        if msg_data.get("code") != 0:
            # Drop a possibly-stale cached token so the next push re-fetches
            # (e.g. after a secret rotation invalidates it server-side).
            _lark_token_cache.pop(app_id, None)
            raise RuntimeError(
                f"Lark API error: code={msg_data.get('code')} msg={msg_data.get('msg')}"
            )


# Maps a channel_type to the AuthorType used when recording a pushed message in
# chat history. Kept in sync with the send-dispatch branches in push_to_team.
_PUSH_THREAD_TYPES = {
    "telegram": AuthorType.TELEGRAM,
    "wechat": AuthorType.WECHAT,
    "lark": AuthorType.LARK,
}


async def push_to_team(team_id: str, text: str) -> bool:
    """Push a message to the team's default push channel.

    Returns True if message was sent, False if no channel configured or on error.
    Errors are logged but never raised.
    """
    try:
        push_target = await get_push_channel(team_id)
        if not push_target:
            return False

        channel_type, raw_chat_id = push_target

        # Load channel credentials
        channel = await TeamChannel.get(team_id, channel_type)
        if not channel or not channel.enabled or not channel.config:
            logger.warning(
                "Push channel %s not available for team %s", channel_type, team_id
            )
            return False

        # Send via channel using typed config models
        if channel_type == "telegram":
            try:
                tg_config = TelegramChannelConfig.model_validate(channel.config)
            except Exception:
                logger.warning("Invalid Telegram config for team %s", team_id)
                return False
            await _send_telegram(tg_config.token, raw_chat_id, text)

        elif channel_type == "wechat":
            try:
                wx_config = WechatChannelConfig.model_validate(channel.config)
            except Exception:
                logger.warning("Invalid WeChat config for team %s", team_id)
                return False

            # Get context_token from runtime data
            channel_data = await TeamChannelData.get(team_id, "wechat")
            wx_data = None
            if channel_data and channel_data.data:
                try:
                    wx_data = WechatChannelData.model_validate(channel_data.data)
                except Exception:
                    pass
            if not wx_data or not wx_data.context_token:
                logger.warning(
                    "No WeChat context_token for team %s (no messages received yet?)",
                    team_id,
                )
                return False

            await _send_wechat(
                wx_config.baseurl,
                wx_config.bot_token,
                wx_config.ilink_bot_id,
                raw_chat_id,
                wx_data.context_token,
                _rewrite_for_wechat(text),
            )

        elif channel_type == "lark":
            try:
                lark_config = LarkChannelConfig.model_validate(channel.config)
            except Exception:
                logger.warning("Invalid Lark config for team %s", team_id)
                return False

            await _send_lark(
                lark_config.app_id,
                lark_config.app_secret,
                lark_config.domain,
                raw_chat_id,
                text,
            )
        else:
            logger.warning("Unknown channel type %s for team %s", channel_type, team_id)
            return False

        # Record message in chat system
        try:
            from intentkit.core.chat import append_agent_message

            lead_chat_id = build_channel_chat_id(channel_type, team_id, raw_chat_id)
            thread_type = _PUSH_THREAD_TYPES[channel_type]

            await append_agent_message(
                agent_id=f"team-{team_id}",
                chat_id=lead_chat_id,
                text=text,
                thread_type=thread_type,
            )
        except Exception:
            logger.warning(
                "Failed to record push message for team %s", team_id, exc_info=True
            )

        logger.info("Pushed message to team %s via %s", team_id, channel_type)
        return True

    except WechatPushWindowClosedError:
        logger.info(
            "Skipped push to team %s: WeChat session window closed (user inactive)",
            team_id,
        )
        return False
    except Exception:
        logger.exception("Failed to push message to team %s", team_id)
        return False
