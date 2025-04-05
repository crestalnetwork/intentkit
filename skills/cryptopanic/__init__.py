"""CryptoPanic skill module."""

import logging
from typing import NotRequired, TypedDict

from abstracts.skill import SkillStoreABC
from skills.cryptopanic.base import CryptopanicBaseTool
from skills.cryptopanic.fetch_crypto_sentiment import FetchCryptoSentiment
from skills.cryptopanic.fetch_crypto_news import FetchCryptoNews
from skills.base import SkillConfig, SkillState

logger = logging.getLogger(__name__)

_cache: dict[str, CryptopanicBaseTool] = {}

class SkillStates(TypedDict):
    fetch_crypto_sentiment: SkillState
    fetch_crypto_news: SkillState

class Config(SkillConfig):
    states: SkillStates
    api_key: str

async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[CryptopanicBaseTool]:
    logger.info("Loading cryptopanic skills")
    available_skills = []

    for skill_name, state in config["states"].items():
        logger.debug(f"Checking skill: {skill_name}, state: {state}")
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result = []
    for name in available_skills:
        skill = get_cryptopanic_skill(name, store)
        if skill:
            logger.info(f"Loaded skill: {name}")
            result.append(skill)
    return result

def get_cryptopanic_skill(
    name: str,
    store: SkillStoreABC,
) -> CryptopanicBaseTool:
    if name == "fetch_crypto_sentiment":
        if name not in _cache:
            _cache[name] = FetchCryptoSentiment(skill_store=store)
        return _cache[name]
    elif name == "fetch_crypto_news":
        if name not in _cache:
            _cache[name] = FetchCryptoNews(skill_store=store)
        return _cache[name]
    else:
        logger.warning(f"Unknown skill: {name}")
        return None
