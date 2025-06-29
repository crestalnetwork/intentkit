"""Base class for Heurist AI skills."""

from typing import Type

from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill


class HeuristBaseTool(IntentKitSkill):
    """Base class for all Heurist AI skills.

    This class provides common functionality for all Heurist AI skills.
    """

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    @property
    def category(self) -> str:
        return "heurist"
