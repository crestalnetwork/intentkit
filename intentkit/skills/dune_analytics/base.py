"""Base module for Dune Analytics skills.

Provides shared functionality for interacting with the Dune Analytics API.
"""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill


class DuneBaseTool(IntentKitSkill):
    """Base class for Dune Analytics skills.

    Offers common functionality like API key retrieval and Dune API interaction.
    """

    category: str = "dune_analytics"

    def get_api_key(self):
        if not config.dune_api_key:
            raise ToolException("Dune Analytics API key is not configured")
        return config.dune_api_key
