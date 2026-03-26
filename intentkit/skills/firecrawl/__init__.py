"""Firecrawl skills for web scraping and crawling."""

import logging
from typing import NotRequired, TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.firecrawl.base import FirecrawlBaseTool
from intentkit.skills.firecrawl.clear import FirecrawlClearIndexedContent
from intentkit.skills.firecrawl.crawl import FirecrawlCrawl
from intentkit.skills.firecrawl.query import FirecrawlQueryIndexedContent
from intentkit.skills.firecrawl.scrape import FirecrawlScrape

# Cache skills at the system level, because they are stateless
_cache: dict[str, FirecrawlBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    firecrawl_scrape: SkillState
    firecrawl_crawl: SkillState
    firecrawl_query_indexed_content: SkillState
    firecrawl_clear_indexed_content: SkillState


class Config(SkillConfig):
    """Configuration for Firecrawl skills."""

    states: SkillStates
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[FirecrawlBaseTool]:
    """Get all Firecrawl skills.

    Args:
        config: The configuration for Firecrawl skills.
        is_private: Whether to include private skills.

    Returns:
        A list of Firecrawl skills.
    """
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [s for name in available_skills if (s := get_firecrawl_skill(name))]


def get_firecrawl_skill(
    name: str,
) -> FirecrawlBaseTool | None:
    """Get a Firecrawl skill by name."""
    if name == "firecrawl_scrape":
        if name not in _cache:
            _cache[name] = FirecrawlScrape()
        return _cache[name]
    elif name == "firecrawl_crawl":
        if name not in _cache:
            _cache[name] = FirecrawlCrawl()
        return _cache[name]
    elif name == "firecrawl_query_indexed_content":
        if name not in _cache:
            _cache[name] = FirecrawlQueryIndexedContent()
        return _cache[name]
    elif name == "firecrawl_clear_indexed_content":
        if name not in _cache:
            _cache[name] = FirecrawlClearIndexedContent()
        return _cache[name]
    else:
        logger.warning("Unknown Firecrawl skill: %s", name)
        return None


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return bool(system_config.firecrawl_api_key)
