"""Base class for Heurist AI skills."""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class HeuristBaseTool(IntentKitSkill):
    """Base class for all Heurist AI skills.

    This class provides common functionality for all Heurist AI skills.
    """

    def get_api_key(self):
        if not config.heurist_api_key:
            raise ToolException("Heurist API key is not configured")
        return config.heurist_api_key

    category: str = "heurist"
