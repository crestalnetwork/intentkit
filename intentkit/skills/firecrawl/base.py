from typing import Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill


class FirecrawlBaseTool(IntentKitSkill):
    """Base class for Firecrawl tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self) -> str:
        """Get the Firecrawl API key from configuration."""
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
                f"Invalid API key provider: {api_key_provider}. Only 'agent_owner' is supported for Firecrawl."
            )

    @property
    def category(self) -> str:
        return "firecrawl"
