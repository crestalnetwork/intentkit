"""CryptoPanic tool module for IntentKit.

Loads and initializes tools for fetching crypto news and providing market insights using CryptoPanic API.
"""

import logging

from intentkit.config.config import config as system_config
from intentkit.tools.meta import ToolsetMeta

from .base import CryptopanicBaseTool

toolset = ToolsetMeta(
    title="CryptoPanic",
    description="CryptoPanic is a news aggregator platform indicating impact on price and market for traders and cryptocurrency enthusiasts.",
    tags=["Analytics", "Crypto", "Knowledge Base"],
    icon="/tools/cryptopanic/cryptopanic.png",
)


logger = logging.getLogger(__name__)

# Cache for tool instances
_tool_cache: dict[str, CryptopanicBaseTool] = {}


async def get_tools(tool_names: list[str], **_) -> list[CryptopanicBaseTool]:
    """Get the requested CryptoPanic tools."""
    return [tool for name in tool_names if (tool := get_cryptopanic_tool(name))]


def get_cryptopanic_tool(tool_name: str) -> CryptopanicBaseTool | None:
    """Retrieve a CryptoPanic tool instance by name.

    Args:
        tool_name: Name of the tool (e.g., 'fetch_crypto_news', 'fetch_crypto_sentiment').

    Returns:
        CryptoPanic tool instance or None if not found or import fails.
    """
    if tool_name in _tool_cache:
        return _tool_cache[tool_name]

    try:
        if tool_name == "fetch_crypto_news":
            from .fetch_crypto_news import FetchCryptoNews

            _tool_cache[tool_name] = FetchCryptoNews()
        elif tool_name == "fetch_crypto_sentiment":
            from .fetch_crypto_sentiment import FetchCryptoSentiment

            _tool_cache[tool_name] = FetchCryptoSentiment()
        else:
            logger.warning("Unknown CryptoPanic tool: %s", tool_name)
            return None

        return _tool_cache[tool_name]

    except ImportError as e:
        logger.error("Failed to import CryptoPanic tool %s: %s", tool_name, e)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.cryptopanic_api_key)
