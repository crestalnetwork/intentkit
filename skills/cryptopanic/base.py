"""Base module for CryptoPanic skills.

Defines the base class and shared utilities for CryptoPanic skills.
"""

from typing import Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill, SkillContext

base_url = "https://cryptopanic.com/api/v1/posts/"


class CryptopanicBaseTool(IntentKitSkill):
    """Base class for CryptoPanic skills.

    Provides common functionality for interacting with the CryptoPanic API,
    including API key retrieval and skill store access.
    """

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    def get_api_key(self, context: SkillContext) -> str:
        """Retrieve the CryptoPanic API key from context.

        Args:
            context: Skill context containing configuration.

        Returns:
            API key string.

        Raises:
            ToolException: If the API key is not found.
        """
        api_key = context.config.get("api_key")
        if not api_key:
            raise ToolException(
                "CryptoPanic API key not found in context.config['api_key']"
            )
        return api_key

    @property
    def category(self) -> str:
        """Category of the skill."""
        return "cryptopanic"
