from typing import Type
from pydantic import BaseModel, Field
from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill

class SolanaTokenRankBaseTool(IntentKitSkill):
    """Base class for Solana Token Rank tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="The skill store for persisting data")

    @property
    def category(self) -> str:
        return "solana_token_rank"
      
