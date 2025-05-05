"""CryptoPanic skill module for IntentKit.

Loads and initializes skills for fetching crypto news and providing market insights using CryptoPanic API.
"""

import logging
from typing import Dict, List, Optional, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState

from .base import CryptopanicBaseTool

logger = logging.getLogger(__name__)

# Cache for skill instances
_skill_cache: Dict[str, CryptopanicBaseTool] = {}


class SkillStates(TypedDict):
    """Type definition for CryptoPanic skill states."""

    fetch_crypto_news: SkillState
    fetch_crypto_sentiment: SkillState


class Config(SkillConfig):
    """Configuration schema for CryptoPanic skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: Config,
    is_private: bool,
    store: SkillStoreABC,
    **kwargs,
) -> List[CryptopanicBaseTool]:
    """Load CryptoPanic skills based on configuration.

    Args:
        config: Skill configuration with states and API key.
        is_private: Whether the context is private (affects skill visibility).
        store: Skill store for accessing other skills.
        **kwargs: Additional keyword arguments.

    Returns:
        List of loaded CryptoPanic skill instances.
    """
    logger.info("Loading CryptoPanic skills")
    available_skills = []

    for skill_name, state in config["states"].items():
        logger.debug("Checking skill: %s, state: %s", skill_name, state)
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    loaded_skills = []
    for name in available_skills:
        skill = get_cryptopanic_skill(name, store)
        if skill:
            logger.info("Successfully loaded skill: %s", name)
            loaded_skills.append(skill)
        else:
            logger.warning("Failed to load skill: %s", name)

    return loaded_skills


def get_cryptopanic_skill(
    name: str,
    store: SkillStoreABC,
) -> Optional[CryptopanicBaseTool]:
    """Retrieve a CryptoPanic skill instance by name.

    Args:
        name: Name of the skill (e.g., 'fetch_crypto_news', 'fetch_crypto_sentiment').
        store: Skill store for accessing other skills.

    Returns:
        CryptoPanic skill instance or None if not found or import fails.
    """
    if name in _skill_cache:
        logger.debug("Retrieved cached skill: %s", name)
        return _skill_cache[name]

    try:
        if name == "fetch_crypto_news":
            from .fetch_crypto_news import FetchCryptoNews

            _skill_cache[name] = FetchCryptoNews(skill_store=store)
        elif name == "fetch_crypto_sentiment":
            from .fetch_crypto_sentiment import FetchCryptoSentiment

            _skill_cache[name] = FetchCryptoSentiment(skill_store=store)
        else:
            logger.warning("Unknown CryptoPanic skill: %s", name)
            return None

        logger.debug("Cached new skill instance: %s", name)
        return _skill_cache[name]

    except ImportError as e:
        logger.error("Failed to import CryptoPanic skill %s: %s", name, e)
        return None
