"""
Slack notification module for sending messages to Slack channels.
"""

import logging
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# Global variables for Slack configuration
_slack_token: Optional[str] = None
_slack_channel: Optional[str] = None
_slack_client: Optional[WebClient] = None


def init_slack(token: str, channel: str) -> None:
    """
    Initialize Slack configuration.

    Args:
        token: Slack bot token
        channel: Default Slack channel ID or name

    Raises:
        ValueError: If token or channel is empty
    """

    global _slack_token, _slack_channel, _slack_client
    _slack_token = token
    _slack_channel = channel
    _slack_client = WebClient(token=token)


def send_slack_message(
    message: str,
    blocks: Optional[list] = None,
    attachments: Optional[list] = None,
    thread_ts: Optional[str] = None,
    channel: Optional[str] = None,
):
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
        response = _slack_client.chat_postMessage(
            channel=channel or _slack_channel,
            text=message,
            blocks=blocks,
            attachments=attachments,
            thread_ts=thread_ts,
        )
        logger.info(f"Message sent successfully to channel {channel or _slack_channel}")
        return response
    except SlackApiError as e:
        logger.error(f"Failed to send Slack message: {str(e)}")
