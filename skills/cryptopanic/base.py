"""Base class for CryptoPanic skills."""

from typing import Optional, Type

from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from app.config.config import config
from skills.base import IntentKitSkill, SkillContext

base_url = "https://cryptopanic.com/api/v1/posts/"

class CryptopanicBaseTool(IntentKitSkill):
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    def get_api_key(self, context: SkillContext) -> Optional[str]:
        return context.config["api_key"]  # only skill config

    @property
    def category(self) -> str:
        return "cryptopanic"
