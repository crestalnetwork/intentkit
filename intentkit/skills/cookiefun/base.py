import logging

from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)


class CookieFunBaseTool(IntentKitSkill):
    """Base class for CookieFun tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    @property
    def category(self) -> str:
        return "cookiefun"

    def get_api_key(self) -> str:
        """
        Get the API key from configuration.

        Returns:
            The API key

        Raises:
            ToolException: If the API key is not found or provider is invalid.
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
                f"Invalid API key provider: {api_key_provider}. Only 'agent_owner' is supported for CookieFun."
            )
