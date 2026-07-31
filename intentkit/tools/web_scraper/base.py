from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool


class WebScraperBaseTool(IntentKitTool):
    """Base class for web scraper tools."""

    category: str = "web_scraper"

    def agent_id_for_log(self) -> str:
        """Best-effort agent id for error-log labels; falls back to UNKNOWN."""
        try:
            context = self.get_context()
            if context and context.agent_id:
                return context.agent_id
        except Exception:  # noqa: S110 - label lookup must never mask the real error
            pass
        return "UNKNOWN"

    def get_openai_api_key(self) -> str:
        """Retrieve the OpenAI API key for embedding operations."""
        if not config.openai_api_key:
            raise ToolException("OpenAI API key is not configured")
        return config.openai_api_key
