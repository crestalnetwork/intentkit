"""Base class for music generation tools."""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool


class MusicBaseTool(IntentKitTool):
    """Shared configuration for music generation tools."""

    category: str = "music"

    def get_api_key(self) -> str:
        """Return the configured API key or raise a tool error."""
        if not config.minimax_plan_api_key:
            raise ToolException("Music generation API key is not configured")
        return config.minimax_plan_api_key
