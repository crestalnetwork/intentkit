from typing import Optional, Type

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
