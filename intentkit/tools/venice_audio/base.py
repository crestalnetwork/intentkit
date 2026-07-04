from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool


class VeniceAudioBaseTool(IntentKitTool):
    """Base class for Venice Audio tools."""

    category: str = "venice_audio"

    def get_api_key(self) -> str:
        if not config.venice_api_key:
            raise ToolException("Venice API key is not configured")
        return config.venice_api_key
