from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill

ELFA_BASE_URL = "https://api.elfa.ai/v2"


class ElfaBaseTool(IntentKitSkill):
    """Base class for Elfa tools."""

    def get_api_key(self):
        if not config.elfa_api_key:
            raise ToolException("Elfa API key is not configured")
        return config.elfa_api_key

    category: str = "elfa"
