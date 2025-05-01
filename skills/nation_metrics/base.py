"""Base module for Crestal Nation skills.

Defines the base class and shared utilities for Crestal Nation skills.
"""

from typing import Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill, SkillContext

BASE_URL = "https://api.dune.com/api/v1/query/"


class NationBaseTool(IntentKitSkill):
    """Base class for Crestal Nation skills.

    Provides common functionality for interacting with the Dune Analytics API,
    including API key retrieval and skill store access.
    """

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    def get_api_key(self, context: SkillContext) -> str:
        """Retrieve the Dune Analytics API key from context.

        Args:
            context: Skill context containing configuration.

        Returns:
            API key string.

        Raises:
            ToolException: If the API key is not found.
        """
        api_key = context.config.get("api_key")
        if not api_key:
            raise ToolException("Dune API key not found in context.config['api_key']")
        return api_key

    @property
    def category(self) -> str:
        """Category of the skill."""
        return "nation_metrics"
