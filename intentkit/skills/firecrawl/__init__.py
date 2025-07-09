"""Firecrawl skills for web scraping and crawling."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
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
    api_key: str = ""
    api_key_provider: str = "agent_owner"
    rate_limit_number: int = 100
    rate_limit_minutes: int = 60


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[FirecrawlBaseTool]:
    """Get all Firecrawl skills.

    Args:
        config: The configuration for Firecrawl skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

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
    return [get_firecrawl_skill(name, store) for name in available_skills]


def get_firecrawl_skill(
    name: str,
    store: SkillStoreABC,
) -> FirecrawlBaseTool:
    """Get a Firecrawl skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Firecrawl skill

    Raises:
        ValueError: If the skill name is unknown
    """
    if name == "firecrawl_scrape":
        if name not in _cache:
            _cache[name] = FirecrawlScrape(
                skill_store=store,
            )
        return _cache[name]
    elif name == "firecrawl_crawl":
        if name not in _cache:
            _cache[name] = FirecrawlCrawl(
                skill_store=store,
            )
        return _cache[name]
    elif name == "firecrawl_query_indexed_content":
        if name not in _cache:
            _cache[name] = FirecrawlQueryIndexedContent(
                skill_store=store,
            )
        return _cache[name]
    elif name == "firecrawl_clear_indexed_content":
        if name not in _cache:
            _cache[name] = FirecrawlClearIndexedContent(
                skill_store=store,
            )
        return _cache[name]
    else:
        raise ValueError(f"Unknown Firecrawl skill: {name}")
