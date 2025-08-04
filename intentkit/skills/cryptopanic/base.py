"""Base module for CryptoPanic skills.

Defines the base class and shared utilities for CryptoPanic skills.
"""

from typing import Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill

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

    def get_api_key(self) -> str:
        """Retrieve the CryptoPanic API key from context.

        Returns:
            API key string.

        Raises:
            ToolException: If the API key is not found.
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "agent_owner":
            api_key = skill_config.get("api_key")
            if api_key:
                return api_key
            else:
                raise ToolException("No api_key found in agent_owner configuration")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}. Only 'agent_owner' is supported for CryptoPanic."
            )

    @property
    def category(self) -> str:
        """Category of the skill."""
        return "cryptopanic"
