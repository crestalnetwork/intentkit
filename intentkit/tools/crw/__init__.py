"""fastCRW tools for web scraping and crawling.

fastCRW is a Firecrawl-compatible web scraper that ships as a single binary and
runs self-hosted or on the managed cloud at https://fastcrw.com. This toolset
mirrors the Firecrawl provider with a different base URL (CRW_API_URL) and key
(CRW_API_KEY); it is additive and does not affect the Firecrawl toolset.
"""

import logging
from typing import NotRequired, TypedDict

from intentkit.config.config import config as system_config
from intentkit.tools.base import ToolsetConfig, ToolState
from intentkit.tools.crw.base import CrwBaseTool
from intentkit.tools.crw.clear import CrwClearIndexedContent
from intentkit.tools.crw.crawl import CrwCrawl
from intentkit.tools.crw.query import CrwQueryIndexedContent
from intentkit.tools.crw.scrape import CrwScrape

# Cache tools at the system level, because they are stateless
_cache: dict[str, CrwBaseTool] = {}

logger = logging.getLogger(__name__)


class ToolStates(TypedDict):
    crw_scrape: ToolState
    crw_crawl: ToolState
    crw_query_indexed_content: ToolState
    crw_clear_indexed_content: ToolState


class Config(ToolsetConfig):
    """Configuration for fastCRW tools."""

    states: ToolStates
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_tools(
    config: "Config",
    is_private: bool,
    **_,
) -> list[CrwBaseTool]:
    """Get all fastCRW tools.

    Args:
        config: The configuration for fastCRW tools.
        is_private: Whether to include private tools.

    Returns:
        A list of fastCRW tools.
    """
    available_tools = []

    # Include tools based on their state
    for tool_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_tools.append(tool_name)

    # Get each tool using the cached getter
    return [s for name in available_tools if (s := get_crw_tool(name))]


def get_crw_tool(
    name: str,
) -> CrwBaseTool | None:
    """Get a fastCRW tool by name."""
    if name == "crw_scrape":
        if name not in _cache:
            _cache[name] = CrwScrape()
        return _cache[name]
    elif name == "crw_crawl":
        if name not in _cache:
            _cache[name] = CrwCrawl()
        return _cache[name]
    elif name == "crw_query_indexed_content":
        if name not in _cache:
            _cache[name] = CrwQueryIndexedContent()
        return _cache[name]
    elif name == "crw_clear_indexed_content":
        if name not in _cache:
            _cache[name] = CrwClearIndexedContent()
        return _cache[name]
    else:
        logger.warning("Unknown fastCRW tool: %s", name)
        return None


def available() -> bool:
    """Check if this toolset is available based on system config.

    fastCRW self-host may run without auth, and CRW_API_URL always has a default,
    so the toolset is available when a key or a custom base URL is configured.
    """
    return bool(system_config.crw_api_key) or bool(
        system_config.crw_api_url
        and system_config.crw_api_url != "https://fastcrw.com/api"
    )
