from typing import Type
from pydantic import BaseModel, Field
from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill


class CoinGeckoBaseTool(IntentKitSkill):
    """Base class for CoinGecko-related tools."""

    name: str = Field(description="Name of the CoinGecko tool")
    description: str = Field(description="Description of the CoinGecko tool's function")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill data storage")

    @property
    def category(self) -> str:
        return "coingecko"
