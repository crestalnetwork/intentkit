from typing import Any

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.slack.base import SlackBaseTool, SlackChannel


class SlackGetChannelSchema(BaseModel):
    """Input schema for SlackGetChannel."""

    channel_id: str | None = Field(
        None,
        description="Channel ID (provide either ID or name)",
    )
    channel_name: str | None = Field(
        None,
        description="Channel name (provide either ID or name)",
    )


class SlackGetChannel(SlackBaseTool):
    """Tool for getting information about a Slack channel."""

    name: str = "slack_get_channel"
    description: str = "Get information about a Slack channel by ID or name"
    args_schema: ArgsSchema | None = SlackGetChannelSchema

    async def _arun(
        self,
        channel_id: str | None = None,
        channel_name: str | None = None,
        **kwargs,
    ) -> SlackChannel | dict[str, SlackChannel]:
        """Run the tool to get information about a Slack channel.

        Args:
            channel_id: The ID of the channel to get information about
            channel_name: The name of the channel to get information about

        Returns:
            Information about the requested channel or all channels if no ID/name provided

        Raises:
            ValueError: If neither channel_id nor channel_name is provided
            Exception: If an error occurs getting the channel information
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        token = skill_config.get("slack_bot_token")
        if not token:
            raise ToolException("Missing required slack_bot_token in configuration")
        client = self.get_client(token)

        try:
            # If no channel specified, return a dict of all channels
            if not channel_id and not channel_name:
                # Get all channels
                response = client.conversations_list()
                if response["ok"]:
                    channels: dict[str, SlackChannel] = {}
                    channel_list = response.get("channels") or []
                    for channel in channel_list:
                        channels[channel["id"]] = self._format_channel(channel)
                    return channels
                else:
                    raise ToolException(f"Error getting channels: {response['error']}")

            # First try to find by channel_id if provided
            if channel_id:
                response = client.conversations_info(channel=channel_id)
                if response["ok"]:
                    channel_data = response.get("channel")
                    if channel_data is None:
                        raise ToolException("Channel data missing from response")
                    return self._format_channel(channel_data)
                else:
                    raise ToolException(f"Error getting channel: {response['error']}")

            # Otherwise try to find by channel_name
            if channel_name:
                # If channel name doesn't start with #, add it
                if not channel_name.startswith("#"):
                    channel_name = f"#{channel_name}"

                # Get all channels and filter by name
                response = client.conversations_list()
                if response["ok"]:
                    channel_list = response.get("channels") or []
                    for channel in channel_list:
                        if channel["name"] == channel_name.lstrip("#"):
                            return self._format_channel(channel)
                    raise ToolException(f"Channel {channel_name} not found")
                else:
                    raise ToolException(f"Error getting channels: {response['error']}")

            raise ToolException("No channel_id or channel_name provided")

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Error getting channel information: {str(e)}")

    def _format_channel(self, channel: dict[str, Any]) -> SlackChannel:
        """Format the channel data into a SlackChannel model.

        Args:
            channel: The raw channel data from the Slack API

        Returns:
            A formatted SlackChannel object
        """
        return SlackChannel(
            id=channel["id"],
            name=channel["name"],
            is_private=channel.get("is_private", False),
            created=channel.get("created", 0),
            creator=channel.get("creator", ""),
            is_archived=channel.get("is_archived", False),
            members=channel.get("members", []),
        )
