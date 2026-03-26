from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.slack.base import SlackBaseTool, SlackMessage


class SlackSendMessageSchema(BaseModel):
    """Input schema for SlackSendMessage."""

    channel_id: str = Field(
        description="Channel ID",
    )
    text: str = Field(
        description="Message text",
    )
    thread_ts: str | None = Field(
        None,
        description="Thread timestamp to reply to",
    )


class SlackSendMessage(SlackBaseTool):
    """Tool for sending messages to a Slack channel or thread."""

    name: str = "slack_send_message"
    description: str = "Send a message to a Slack channel or thread"
    args_schema: ArgsSchema | None = SlackSendMessageSchema

    async def _arun(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
        **kwargs,
    ) -> SlackMessage:
        """Run the tool to send a Slack message.

        Args:
            channel_id: The ID of the channel to send the message to
            text: The text content of the message to send
            thread_ts: The timestamp of the thread to reply to, if sending a thread reply

        Returns:
            Information about the sent message

        Raises:
            Exception: If an error occurs sending the message
        """
        token = self.get_api_key()
        client = self.get_client(token)

        try:
            # Send the message
            response = client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts if thread_ts else None,
            )

            if response["ok"]:
                ts_val = response.get("ts")
                message_data = response.get("message")
                user_val = message_data["user"] if message_data else ""
                return SlackMessage(
                    ts=str(ts_val) if ts_val else "",
                    text=text,
                    user=user_val,
                    channel=channel_id,
                    thread_ts=thread_ts,
                )
            else:
                raise ToolException(f"Error sending message: {response.get('error')}")

        except Exception as e:
            raise ToolException(f"Error sending message: {str(e)}")
