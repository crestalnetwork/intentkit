from typing import Any, Dict, Optional, Type, Union

from pydantic import BaseModel, Field

from intentkit.skills.slack.base import SlackBaseTool, SlackChannel


class SlackGetChannelSchema(BaseModel):
    """Input schema for SlackGetChannel."""

    channel_id: Optional[str] = Field(
        None,
        description="The ID of the channel to get information about. Provide either channel_id or channel_name.",
    )
    channel_name: Optional[str] = Field(
        None,
        description="The name of the channel to get information about. Provide either channel_id or channel_name.",
    )


class SlackGetChannel(SlackBaseTool):
    """Tool for getting information about a Slack channel."""

    name: str = "slack_get_channel"
    description: str = "Get information about a Slack channel by ID or name"
    args_schema: Type[BaseModel] = SlackGetChannelSchema

    async def _arun(
        self,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        **kwargs,
    ) -> Union[SlackChannel, Dict[str, SlackChannel]]:
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
        client = self.get_client(skill_config.get("slack_bot_token"))

        try:
            # If no channel specified, return a dict of all channels
            if not channel_id and not channel_name:
                # Get all channels
                response = client.conversations_list()
                if response["ok"]:
                    channels = {}
                    for channel in response["channels"]:
                        channels[channel["id"]] = self._format_channel(channel)
                    return channels
                else:
                    raise Exception(f"Error getting channels: {response['error']}")

            # First try to find by channel_id if provided
            if channel_id:
                response = client.conversations_info(channel=channel_id)
                if response["ok"]:
                    return self._format_channel(response["channel"])
                else:
                    raise Exception(f"Error getting channel: {response['error']}")

            # Otherwise try to find by channel_name
            if channel_name:
                # If channel name doesn't start with #, add it
                if not channel_name.startswith("#"):
                    channel_name = f"#{channel_name}"

                # Get all channels and filter by name
                response = client.conversations_list()
                if response["ok"]:
                    for channel in response["channels"]:
                        if channel["name"] == channel_name.lstrip("#"):
                            return self._format_channel(channel)
                    raise ValueError(f"Channel {channel_name} not found")
                else:
                    raise Exception(f"Error getting channels: {response['error']}")

        except Exception as e:
            raise Exception(f"Error getting channel information: {str(e)}")

    def _format_channel(self, channel: Dict[str, Any]) -> SlackChannel:
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
