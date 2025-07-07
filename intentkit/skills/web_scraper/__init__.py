"""Web scraper skills for content indexing and retrieval."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillOwnerState, SkillState
from intentkit.skills.web_scraper.base import WebScraperBaseTool
from intentkit.skills.web_scraper.document_indexer import DocumentIndexer
from intentkit.skills.web_scraper.scrape_and_index import (
    QueryIndexedContent,
    ScrapeAndIndex,
)
from intentkit.skills.web_scraper.website_indexer import WebsiteIndexer

# Cache skills at the system level, because they are stateless
_cache: dict[str, WebScraperBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    scrape_and_index: SkillOwnerState
    query_indexed_content: SkillState
    website_indexer: SkillOwnerState
    document_indexer: SkillOwnerState


class Config(SkillConfig):
    """Configuration for web scraper skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[WebScraperBaseTool]:
    """Get all web scraper skills.

    Args:
        config: The configuration for web scraper skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of web scraper skills.
    """
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_web_scraper_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_web_scraper_skill(
    name: str,
    store: SkillStoreABC,
) -> WebScraperBaseTool:
    """Get a web scraper skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested web scraper skill
    """
    if name == "scrape_and_index":
        if name not in _cache:
            _cache[name] = ScrapeAndIndex(
                skill_store=store,
            )
        return _cache[name]
    elif name == "query_indexed_content":
        if name not in _cache:
            _cache[name] = QueryIndexedContent(
                skill_store=store,
            )
        return _cache[name]
    elif name == "website_indexer":
        if name not in _cache:
            _cache[name] = WebsiteIndexer(
                skill_store=store,
            )
        return _cache[name]
    elif name == "document_indexer":
        if name not in _cache:
            _cache[name] = DocumentIndexer(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown web scraper skill: {name}")
        return None
