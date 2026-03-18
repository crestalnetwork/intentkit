"""Base class for OpenAI skills."""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class OpenAIBaseTool(IntentKitSkill):
    """Base class for all OpenAI skills.

    This class provides common functionality for all OpenAI skills.
    """

    def get_api_key(self):
        if not config.openai_api_key:
            raise ToolException("OpenAI API key is not configured")
        return config.openai_api_key

    category: str = "openai"
