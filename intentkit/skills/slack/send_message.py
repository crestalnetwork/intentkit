from typing import Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.slack.base import SlackBaseTool, SlackMessage


class SlackSendMessageSchema(BaseModel):
    """Input schema for SlackSendMessage."""

    channel_id: str = Field(
        description="The ID of the channel to send the message to",
    )
    text: str = Field(
        description="The text content of the message to send",
    )
    thread_ts: Optional[str] = Field(
        None,
        description="The timestamp of the thread to reply to, if sending a thread reply",
    )


class SlackSendMessage(SlackBaseTool):
    """Tool for sending messages to a Slack channel or thread."""

    name: str = "slack_send_message"
    description: str = "Send a message to a Slack channel or thread"
    args_schema: Type[BaseModel] = SlackSendMessageSchema

    async def _arun(
        self,
        channel_id: str,
        text: str,
        thread_ts: Optional[str] = None,
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
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        client = self.get_client(skill_config.get("slack_bot_token"))

        try:
            # Prepare message parameters
            message_params = {
                "channel": channel_id,
                "text": text,
            }

            # Add thread_ts if replying to a thread
            if thread_ts:
                message_params["thread_ts"] = thread_ts

            # Send the message
            response = client.chat_postMessage(**message_params)

            if response["ok"]:
                return SlackMessage(
                    ts=response["ts"],
                    text=text,
                    user=response["message"]["user"],
                    channel=channel_id,
                    thread_ts=thread_ts,
                )
            else:
                raise Exception(f"Error sending message: {response.get('error')}")

        except Exception as e:
            raise Exception(f"Error sending message: {str(e)}")
