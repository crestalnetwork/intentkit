from typing import Optional, Type

from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill, SkillContext

base_url = "https://api.upshot.xyz/v2/allora"


class AlloraBaseTool(IntentKitSkill):
    """Base class for Allora tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self, context: SkillContext) -> Optional[str]:
        if "api_key" in context.config and context.config["api_key"]:
            return context.config["api_key"]
        return self.skill_store.get_system_config("allora_api_key")

    @property
    def category(self) -> str:
        return "allora"
