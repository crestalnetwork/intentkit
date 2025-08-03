"""Base module for Dune Analytics skills.

Provides shared functionality for interacting with the Dune Analytics API.
"""

from typing import Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill


class DuneBaseTool(IntentKitSkill):
    """Base class for Dune Analytics skills.

    Offers common functionality like API key retrieval and Dune API interaction.
    """

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    def get_api_key(self) -> str:
        """Retrieve the Dune Analytics API key from context.

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
                f"Invalid API key provider: {api_key_provider}. Only 'agent_owner' is supported for Dune Analytics."
            )

    @property
    def category(self) -> str:
        """Category of the skill."""
        return "dune_analytics"
