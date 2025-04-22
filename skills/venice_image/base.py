# Creating file: venice_image/base.py
from typing import Optional, Type

from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill, SkillContext

base_url = "https://api.venice.ai"


class VeniceImageBaseTool(IntentKitSkill):
    """Base class for Venice Image tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self, context: SkillContext) -> Optional[str]:
        """Get the API key, prioritizing agent config then system config."""
        if "api_key" in context.config and context.config["api_key"]:
            return context.config["api_key"]
        return self.skill_store.get_system_config("venice_api_key")

    @property
    def category(self) -> str:
        return "venice_image"