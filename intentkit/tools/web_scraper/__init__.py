"""Web scraper tools for content indexing and retrieval."""

from intentkit.config.config import config as system_config
from intentkit.tools.web_scraper.base import WebScraperBaseTool
from intentkit.tools.web_scraper.document_indexer import DocumentIndexer
from intentkit.tools.web_scraper.scrape_and_index import (
    QueryIndexedContent,
    ScrapeAndIndex,
)
from intentkit.tools.web_scraper.website_indexer import WebsiteIndexer

# Cache tools at the system level, because they are stateless
_cache: dict[str, WebScraperBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[WebScraperBaseTool]] = {
    "web_scraper_scrape_and_index": ScrapeAndIndex,
    "web_scraper_query_indexed_content": QueryIndexedContent,
    "web_scraper_website_indexer": WebsiteIndexer,
    "web_scraper_document_indexer": DocumentIndexer,
}


async def get_tools(tool_names: list[str], **_) -> list[WebScraperBaseTool]:
    """Return web scraper tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[WebScraperBaseTool] = []
    for name in tool_names:
        tool = get_web_scraper_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_web_scraper_tool(tool_name: str) -> WebScraperBaseTool | None:
    """Get a web scraper tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.openai_api_key)
