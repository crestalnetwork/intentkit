"""Firecrawl tools for web scraping and crawling."""

from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.firecrawl.base import FirecrawlBaseTool
from intentkit.tools.firecrawl.clear import FirecrawlClearIndexedContent
from intentkit.tools.firecrawl.crawl import FirecrawlCrawl
from intentkit.tools.firecrawl.query import FirecrawlQueryIndexedContent
from intentkit.tools.firecrawl.scrape import FirecrawlScrape

# Cache tools at the system level, because they are stateless
_cache: dict[str, FirecrawlBaseTool] = {}

_TOOL_CLASSES: dict[str, Callable[[], FirecrawlBaseTool]] = {
    "firecrawl_scrape": FirecrawlScrape,
    "firecrawl_crawl": FirecrawlCrawl,
    "firecrawl_query_indexed_content": FirecrawlQueryIndexedContent,
    "firecrawl_clear_indexed_content": FirecrawlClearIndexedContent,
}


async def get_tools(tool_names: list[str], **_) -> list[FirecrawlBaseTool]:
    """Get the requested Firecrawl tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_firecrawl_tool(name))]


def get_firecrawl_tool(tool_name: str) -> FirecrawlBaseTool | None:
    """Get a Firecrawl tool by name, using the instance cache."""
    if tool_name in _cache:
        return _cache[tool_name]
    cls = _TOOL_CLASSES.get(tool_name)
    if cls is None:
        return None
    _cache[tool_name] = cls()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.firecrawl_api_key)
