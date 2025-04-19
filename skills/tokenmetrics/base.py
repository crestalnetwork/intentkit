"""Base module for TokenMetrics skills.

Defines the base class and shared utilities for TokenMetrics skills.
"""

from typing import Optional, Type

from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill, SkillContext

base_url = "https://api.tokenmetrics.com/v2/"


class TokenMetricsBaseTool(IntentKitSkill):
    """Base class for TokenMetrics skills.

    Provides common functionality for interacting with the TokenMetrics API,
    including API key retrieval and skill store access.
    """

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    def get_api_key(self, context: SkillContext) -> Optional[str]:
        """Retrieve the TokenMetrics API key from context or skill store.

        Args:
            context: Skill context containing configuration.

        Returns:
            API key string or None if not found.
        """
        if "api_key" in context.config and context.config["api_key"]:
            return context.config["api_key"]
        return self.skill_store.get_system_config("tokenmetrics_api_key")

    @property
    def category(self) -> str:
        """Category of the skill."""
        return "tokenmetrics"
