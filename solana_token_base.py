from typing import Type
from pydantic import BaseModel, Field
from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill

class SolanaTokenBaseSkill(IntentKitSkill):
    """Base class for Solana token related skills."""

    name: str = Field(description="Name of the skill")
    description: str = Field(description="Skill description")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill store for storing state")

    @property
    def category(self) -> str:
        return "solana_token"
