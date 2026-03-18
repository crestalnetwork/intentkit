"""Base module for CryptoPanic skills.

Defines the base class and shared utilities for CryptoPanic skills.
"""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill

base_url = "https://cryptopanic.com/api/v1/posts/"


class CryptopanicBaseTool(IntentKitSkill):
    """Base class for CryptoPanic skills.

    Provides common functionality for interacting with the CryptoPanic API,
    including API key retrieval and shared helpers.
    """

    category: str = "cryptopanic"

    def get_api_key(self):
        if not config.cryptopanic_api_key:
            raise ToolException("CryptoPanic API key is not configured")
        return config.cryptopanic_api_key
