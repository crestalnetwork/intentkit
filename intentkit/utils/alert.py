"""
Unified alert module for sending notifications to Telegram or Slack.

This module provides a unified interface for sending alert messages.
Based on configuration, it routes messages to either Telegram or Slack.
If neither is configured, messages are logged instead.
"""

import html as html_mod
import logging
from collections.abc import Sequence
from enum import Enum
from typing import Any, Literal

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Alert service type."""

    TELEGRAM = "telegram"
    SLACK = "slack"
    NONE = "none"


# Global state
_alert_type: AlertType = AlertType.NONE
_initialized: bool = False


def init_alert(
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    slack_token: str | None = None,
    slack_channel: str | None = None,
) -> AlertType:
    """
    Initialize alert system based on available configuration.

    Priority: Telegram > Slack > None (log only)

    Args:
        telegram_bot_token: Telegram bot token (obtained from @BotFather)
        telegram_chat_id: Telegram chat ID (user, group, or channel)
        slack_token: Slack bot token
        slack_channel: Slack channel ID or name

    Returns:
        AlertType: The type of alert service that was initialized
    """
    global _alert_type, _initialized

    if _initialized:
        logger.info(
            "Alert system already initialized with %s, skipping reinitialization",
            _alert_type.value,
        )
        return _alert_type

    # Priority: Telegram > Slack
    if telegram_bot_token and telegram_chat_id:
        from intentkit.utils.telegram_alert import init_telegram

        init_telegram(telegram_bot_token, telegram_chat_id)
        _alert_type = AlertType.TELEGRAM
        _initialized = True
        logger.info("Alert system initialized with Telegram")
    elif slack_token and slack_channel:
        from intentkit.utils.slack_alert import init_slack

        init_slack(slack_token, slack_channel)
        _alert_type = AlertType.SLACK
        _initialized = True
        logger.info("Alert system initialized with Slack")
    else:
        _alert_type = AlertType.NONE
        _initialized = True
        logger.info("Alert system initialized without external service (log only)")

    return _alert_type


def cleanup_alert() -> None:
    """
    Cleanup alert resources and reset state.
    """
    global _alert_type, _initialized

    if _alert_type == AlertType.TELEGRAM:
        from intentkit.utils.telegram_alert import cleanup_telegram

        cleanup_telegram()
    elif _alert_type == AlertType.SLACK:
        from intentkit.utils.slack_alert import cleanup_slack

        cleanup_slack()

    _alert_type = AlertType.NONE
    _initialized = False


def get_alert_type() -> AlertType:
    """
    Get the current alert type.

    Returns:
        AlertType: The current alert service type
    """
    return _alert_type


def is_alert_enabled() -> bool:
    """
    Check if an external alert service is enabled.

    Returns:
        bool: True if Telegram or Slack is configured
    """
    return _alert_type != AlertType.NONE


def _format_telegram_message(
    message: str,
    blocks: Sequence[dict[str, Any]] | None = None,
    attachments: Sequence[dict[str, Any]] | None = None,
) -> tuple[str, Literal["HTML", "Markdown", "MarkdownV2"] | None]:
    """
    Format alert content for Telegram by converting Slack-style blocks and attachments.

    Returns:
        A tuple of (formatted_message, parse_mode).
        parse_mode is "HTML" when attachments/blocks are present, None otherwise.
    """
    # Convert Slack-specific syntax in the message
    # <!channel> is Slack's @channel mention
    message = message.replace("<!channel>", "").strip()

    if not blocks and not attachments:
        return message, None

    # Use HTML formatting for structured content
    lines: list[str] = [f"<b>{html_mod.escape(message)}</b>"]

    if attachments:
        for attachment in attachments:
            lines.append("")

            # Color indicator
            color = attachment.get("color", "")
            color_emoji = {"good": "🟢", "danger": "🔴", "warning": "🟡"}.get(
                color, "⚪"
            )

            # Title
            title = attachment.get("title")
            if title:
                lines.append(f"{color_emoji} <b>{html_mod.escape(str(title))}</b>")

            # Text body
            text = attachment.get("text")
            if text:
                lines.append(html_mod.escape(str(text)))

            # Fields (key-value pairs)
            fields = attachment.get("fields")
            if fields:
                for field in fields:
                    field_title = field.get("title", "")
                    field_value = field.get("value", "")
                    lines.append(
                        f"• <b>{html_mod.escape(str(field_title))}</b>: {html_mod.escape(str(field_value))}"
                    )

    if blocks:
        lines.append("")
        for block in blocks:
            # Best-effort: extract text from common Slack block types
            block_type = block.get("type", "")
            if block_type == "section":
                block_text = block.get("text", {})
                if isinstance(block_text, dict):
                    lines.append(html_mod.escape(block_text.get("text", str(block))))
                else:
                    lines.append(html_mod.escape(str(block_text)))
            elif block_type == "header":
                header_text = block.get("text", {})
                if isinstance(header_text, dict):
                    lines.append(
                        f"<b>{html_mod.escape(header_text.get('text', ''))}</b>"
                    )
                else:
                    lines.append(f"<b>{html_mod.escape(str(header_text))}</b>")
            elif block_type == "divider":
                lines.append("───────────")
            else:
                lines.append(html_mod.escape(str(block)))

    return "\n".join(lines).strip(), "HTML"


def send_alert(
    message: str,
    blocks: Sequence[dict[str, Any]] | None = None,
    attachments: Sequence[dict[str, Any]] | None = None,
    thread_ts: str | None = None,
    channel: str | None = None,
) -> None:
    """
    Send an alert message through the configured service.

    For Telegram: Only the message text is sent. blocks, attachments,
                  thread_ts, and channel parameters are ignored.
    For Slack: All parameters are passed through to the Slack API.
    For None: Message is logged at INFO level.

    Args:
        message: The message text to send
        blocks: Optional Slack blocks for rich message formatting
        attachments: Optional Slack attachments for the message
        thread_ts: Optional Slack thread timestamp to reply to a thread
        channel: Optional channel override (Slack only)
    """
    if _alert_type == AlertType.TELEGRAM:
        from intentkit.utils.telegram_alert import send_telegram_message

        telegram_message, parse_mode = _format_telegram_message(
            message=message,
            blocks=blocks,
            attachments=attachments,
        )
        send_telegram_message(telegram_message, parse_mode=parse_mode)

    elif _alert_type == AlertType.SLACK:
        from intentkit.utils.slack_alert import send_slack_message

        send_slack_message(
            message=message,
            blocks=blocks,
            attachments=attachments,
            thread_ts=thread_ts,
            channel=channel,
        )

    else:
        # No alert service configured, log the message
        log_lines = [f"[Alert] {message}"]
        if blocks:
            log_lines.append(f"[Alert blocks] {blocks}")
        if attachments:
            log_lines.append(f"[Alert attachments] {attachments}")
        logger.info("\n".join(log_lines))
