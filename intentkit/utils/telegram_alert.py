"""
Telegram notification module for sending messages to Telegram chats.
"""

import logging
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

# Global variables for Telegram configuration
_telegram_bot_token: str | None = None
_telegram_chat_id: str | None = None
_telegram_client: httpx.Client | None = None


def init_telegram(bot_token: str, chat_id: str) -> None:
    """
    Initialize Telegram configuration.

    Args:
        bot_token: Telegram bot token (obtained from @BotFather)
        chat_id: Default Telegram chat ID (user, group, or channel)

    Raises:
        ValueError: If bot_token or chat_id is empty
    """
    if not bot_token or not chat_id:
        raise ValueError("bot_token and chat_id are required")

    global _telegram_bot_token, _telegram_chat_id, _telegram_client
    _telegram_bot_token = bot_token
    _telegram_chat_id = chat_id
    _telegram_client = httpx.Client(timeout=10)


def cleanup_telegram() -> None:
    """
    Cleanup Telegram client resources and reset configuration.
    """
    global _telegram_bot_token, _telegram_chat_id, _telegram_client
    if _telegram_client:
        _telegram_client.close()
        _telegram_client = None
    _telegram_bot_token = None
    _telegram_chat_id = None


def send_telegram_message(
    message: str,
    parse_mode: Literal["HTML", "Markdown", "MarkdownV2"] | None = None,
    chat_id: str | None = None,
    disable_web_page_preview: bool = True,
    disable_notification: bool = False,
) -> None:
    """
    Send a message to a Telegram chat.

    Args:
        message: The message text to send (max 4096 characters)
        parse_mode: Optional parse mode for formatting (HTML, Markdown, MarkdownV2)
        chat_id: Optional chat ID override. If not provided, uses the default chat ID
        disable_web_page_preview: Whether to disable link previews (default: True)
        disable_notification: Whether to send silently (default: False)

    Raises:
        RuntimeError: If Telegram is not initialized
        httpx.HTTPStatusError: If the message fails to send
    """
    if not _telegram_client or not _telegram_bot_token or not _telegram_chat_id:
        # Write the input message to the log and return
        logger.info("Telegram not initialized")
        logger.info(message)
        return

    target_chat_id = chat_id or _telegram_chat_id
    url = f"https://api.telegram.org/bot{_telegram_bot_token}/sendMessage"

    # Truncate message if too long (Telegram limit is 4096 characters)
    truncated_message = message[:4096]

    payload: dict[str, str | bool] = {
        "chat_id": target_chat_id,
        "text": truncated_message,
        "disable_web_page_preview": disable_web_page_preview,
        "disable_notification": disable_notification,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = _telegram_client.post(url, json=payload)
        _ = response.raise_for_status()
        logger.info(f"Message sent successfully to Telegram chat {target_chat_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        raise
