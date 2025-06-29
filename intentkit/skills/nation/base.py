from typing import Type

from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill

default_nation_api_url = "http://backend-api"


class NationBaseTool(IntentKitSkill):
    """Base class for GitHub tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self) -> str:
        return self.skill_store.get_system_config("nation_api_key")

    def get_base_url(self) -> str:
        if self.skill_store.get_system_config("nation_api_url"):
            return self.skill_store.get_system_config("nation_api_url")
        return default_nation_api_url

    @property
    def category(self) -> str:
        return "nation"
