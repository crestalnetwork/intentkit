from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class DappLookerBaseTool(IntentKitSkill):
    """Base class for DappLooker tools."""

    def get_api_key(self):
        if not config.dapplooker_api_key:
            raise ToolException("DappLooker API key is not configured")
        return config.dapplooker_api_key

    category: str = "dapplooker"
