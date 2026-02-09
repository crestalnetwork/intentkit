from typing import Type
from pydantic import BaseModel, Field
from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill

class HuggingFaceBaseTool(IntentKitSkill):
    """Base class for HuggingFace NLP tools."""

    name: str = Field(description="Tool name")
    description: str = Field(description="What the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    @property
    def category(self) -> str:
        return "huggingface"

