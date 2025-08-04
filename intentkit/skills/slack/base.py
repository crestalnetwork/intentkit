from typing import Optional, Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field
from slack_sdk import WebClient

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill


class SlackBaseTool(IntentKitSkill):
    """Base class for Slack tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self) -> str:
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "agent_owner":
            slack_bot_token = skill_config.get("slack_bot_token")
            if slack_bot_token:
                return slack_bot_token
            else:
                raise ToolException(
                    "No slack_bot_token found in agent_owner configuration"
                )
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}. Only 'agent_owner' is supported for Slack."
            )

    @property
    def category(self) -> str:
        return "slack"

    def get_client(self, token: str) -> WebClient:
        """Get a Slack WebClient instance.

        Args:
            token: The Slack bot token to use

        Returns:
            WebClient: A configured Slack client
        """
        return WebClient(token=token)


class SlackChannel(BaseModel):
    """Model representing a Slack channel."""

    id: str
    name: str
    is_private: bool
    created: int
    creator: str
    is_archived: bool
    members: list[str] = []


class SlackMessage(BaseModel):
    """Model representing a Slack message."""

    ts: str
    text: str
    user: str
    channel: str
    thread_ts: Optional[str] = None
