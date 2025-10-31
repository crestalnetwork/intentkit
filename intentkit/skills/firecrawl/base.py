from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class FirecrawlBaseTool(IntentKitSkill):
    """Base class for Firecrawl tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

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
            return config.firecrawl_api_key

    @property
    def category(self) -> str:
        return "firecrawl"
