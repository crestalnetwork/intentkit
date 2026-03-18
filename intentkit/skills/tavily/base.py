from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class TavilyBaseTool(IntentKitSkill):
    """Base class for Tavily search tools."""

    def get_api_key(self):
        if not config.tavily_api_key:
            raise ToolException("Tavily API key is not configured")
        return config.tavily_api_key

    category: str = "tavily"
