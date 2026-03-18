from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class FirecrawlBaseTool(IntentKitSkill):
    """Base class for Firecrawl tools."""

    def get_api_key(self):
        if not config.firecrawl_api_key:
            raise ToolException("Firecrawl API key is not configured")
        return config.firecrawl_api_key

    category: str = "firecrawl"
