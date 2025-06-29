"""Base class for OpenAI skills."""

from typing import Type

from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill, SkillContext


class OpenAIBaseTool(IntentKitSkill):
    """Base class for all OpenAI skills.

    This class provides common functionality for all OpenAI skills.
    """

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self, context: SkillContext) -> str:
        skill_config = context.config
        if skill_config.get("api_key_provider") == "agent_owner":
            return skill_config.get("api_key")
        return self.skill_store.get_system_config("openai_api_key")

    @property
    def category(self) -> str:
        return "openai"
