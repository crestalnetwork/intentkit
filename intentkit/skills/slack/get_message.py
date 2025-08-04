from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.slack.base import SlackBaseTool, SlackMessage


class SlackGetMessageSchema(BaseModel):
    """Input schema for SlackGetMessage."""

    channel_id: str = Field(
        description="The ID of the channel containing the message",
    )
    ts: Optional[str] = Field(
        None,
        description="The timestamp of a specific message to retrieve. If not provided, returns recent messages.",
    )
    thread_ts: Optional[str] = Field(
        None,
        description="If provided, retrieve messages from this thread instead of the channel.",
    )
    limit: Optional[int] = Field(
        10,
        description="The maximum number of messages to return (1-100, default 10).",
    )


class SlackGetMessage(SlackBaseTool):
    """Tool for getting messages from a Slack channel or thread."""

    name: str = "slack_get_message"
    description: str = "Get messages from a Slack channel or thread"
    args_schema: Type[BaseModel] = SlackGetMessageSchema

    async def _arun(
        self,
        channel_id: str,
        ts: Optional[str] = None,
        thread_ts: Optional[str] = None,
        limit: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        """Run the tool to get Slack messages.

        Args:
            channel_id: The ID of the channel to get messages from
            ts: The timestamp of a specific message to retrieve
            thread_ts: If provided, retrieve messages from this thread
            limit: Maximum number of messages to return (1-100)

        Returns:
            A dictionary containing the requested messages

        Raises:
            Exception: If an error occurs getting the messages
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        client = self.get_client(skill_config.get("slack_bot_token"))

        try:
            # Ensure limit is within bounds
            if limit < 1:
                limit = 1
            elif limit > 100:
                limit = 100

            # Get a specific message by timestamp
            if ts and not thread_ts:
                response = client.conversations_history(
                    channel=channel_id, latest=ts, limit=1, inclusive=True
                )
                if response["ok"] and response["messages"]:
                    return {
                        "messages": [
                            self._format_message(response["messages"][0], channel_id)
                        ]
                    }
                else:
                    raise Exception(f"Message with timestamp {ts} not found")

            # Get messages from a thread
            elif thread_ts:
                response = client.conversations_replies(
                    channel=channel_id, ts=thread_ts, limit=limit
                )
                if response["ok"]:
                    return {
                        "messages": [
                            self._format_message(msg, channel_id)
                            for msg in response["messages"]
                        ],
                        "has_more": response.get("has_more", False),
                    }
                else:
                    raise Exception(
                        f"Error getting thread messages: {response.get('error')}"
                    )

            # Get channel history
            else:
                response = client.conversations_history(channel=channel_id, limit=limit)
                if response["ok"]:
                    return {
                        "messages": [
                            self._format_message(msg, channel_id)
                            for msg in response["messages"]
                        ],
                        "has_more": response.get("has_more", False),
                    }
                else:
                    raise Exception(
                        f"Error getting channel messages: {response.get('error')}"
                    )

        except Exception as e:
            raise Exception(f"Error getting messages: {str(e)}")

    def _format_message(self, message: Dict[str, Any], channel_id: str) -> SlackMessage:
        """Format the message data into a SlackMessage model.

        Args:
            message: The raw message data from the Slack API
            channel_id: The channel ID the message belongs to

        Returns:
            A formatted SlackMessage object
        """
        return SlackMessage(
            ts=message["ts"],
            text=message["text"],
            user=message.get("user", ""),
            channel=channel_id,
            thread_ts=message.get("thread_ts"),
        )
