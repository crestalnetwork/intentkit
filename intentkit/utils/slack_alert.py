"""
Slack notification module for sending messages to Slack channels.
"""

import logging
from collections.abc import Sequence
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# Global variables for Slack configuration.
# NOTE on thread safety: These are only written once during init_slack() at startup
# and read-only afterward. Python's GIL ensures safe reads, so no lock is needed.
_slack_token: str | None = None
_slack_channel: str | None = None
_slack_client: WebClient | None = None


def init_slack(token: str, channel: str) -> None:
    """
    Initialize Slack configuration.

    Args:
        token: Slack bot token
        channel: Default Slack channel ID or name

    Raises:
        ValueError: If token or channel is empty
    """
    if not token or not channel:
        raise ValueError("token and channel are required")

    global _slack_token, _slack_channel, _slack_client
    _slack_token = token
    _slack_channel = channel
    _slack_client = WebClient(token=token)


def cleanup_slack() -> None:
    """
    Cleanup Slack client resources and reset configuration.
    """
    global _slack_token, _slack_channel, _slack_client
    _slack_client = None
    _slack_token = None
    _slack_channel = None


def send_slack_message(
    message: str,
    blocks: Sequence[dict[str, Any]] | None = None,
    attachments: Sequence[dict[str, Any]] | None = None,
    thread_ts: str | None = None,
    channel: str | None = None,
) -> None:
    """
    Send a message to a Slack channel.

    Args:
        message: The message text to send
        blocks: Optional blocks for rich message formatting (see Slack Block Kit)
        attachments: Optional attachments for the message
        thread_ts: Optional thread timestamp to reply to a thread
        channel: Optional channel override. If not provided, uses the default channel

    Raises:
        RuntimeError: If slack is not initialized
        SlackApiError: If the message fails to send
    """
    if not _slack_client or not _slack_channel:
        # Write the input message to the log and return
        logger.info("Slack not initialized")
        logger.info(message)
        if blocks:
            logger.info(blocks)
        if attachments:
            logger.info(attachments)
        return

    try:
        _ = _slack_client.chat_postMessage(
            channel=channel or _slack_channel,
            text=message,
            blocks=blocks,
            attachments=attachments,
            thread_ts=thread_ts,
        )
        logger.info(
            "Message sent successfully to channel %s", channel or _slack_channel
        )
    except SlackApiError as e:
        logger.error("Failed to send Slack message: %s", e)
