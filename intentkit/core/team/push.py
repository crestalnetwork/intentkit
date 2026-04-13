"""Team channel push functions.

Send proactive messages to a team's default push channel (Telegram or WeChat)
and record them in the chat message system.
"""

import base64
import logging
import random

import httpx
from epyxid import XID

from intentkit.core.team.channel import get_push_channel
from intentkit.models.chat import AuthorType
from intentkit.models.team_channel import (
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
        if data.get("ret") != 0:
            raise RuntimeError(
                f"iLink API error: ret={data.get('ret')} errmsg={data.get('errmsg')}"
            )


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
                text,
            )
        else:
            logger.warning("Unknown channel type %s for team %s", channel_type, team_id)
            return False

        # Record message in chat system
        try:
            from intentkit.core.chat import append_agent_message

            if channel_type == "telegram":
                lead_chat_id = f"tg_team:{team_id}:{raw_chat_id}"
                thread_type = AuthorType.TELEGRAM
            else:
                lead_chat_id = f"wx_team:{team_id}:{raw_chat_id}"
                thread_type = AuthorType.WECHAT

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

    except Exception:
        logger.exception("Failed to push message to team %s", team_id)
        return False
