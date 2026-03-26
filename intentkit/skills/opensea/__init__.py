"""OpenSea NFT marketplace skills."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import IntentKitSkill, SkillConfig, SkillState
from intentkit.skills.opensea.buy_nft import OpenSeaBuyNft
from intentkit.skills.opensea.cancel_listing import OpenSeaCancelListing
from intentkit.skills.opensea.create_listing import OpenSeaCreateListing
from intentkit.skills.opensea.get_collection import OpenSeaGetCollection
from intentkit.skills.opensea.get_collection_stats import OpenSeaGetCollectionStats
from intentkit.skills.opensea.get_events import OpenSeaGetEvents
from intentkit.skills.opensea.get_listings import OpenSeaGetListings
from intentkit.skills.opensea.get_nft import OpenSeaGetNft
from intentkit.skills.opensea.get_nfts_by_account import OpenSeaGetNftsByAccount
from intentkit.skills.opensea.get_offers import OpenSeaGetOffers
from intentkit.skills.opensea.update_listing import OpenSeaUpdateListing

# Cache skills at the system level, because they are stateless
_cache: dict[str, IntentKitSkill] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    opensea_get_collection: SkillState
    opensea_get_collection_stats: SkillState
    opensea_get_nft: SkillState
    opensea_get_listings: SkillState
    opensea_get_offers: SkillState
    opensea_get_events: SkillState
    opensea_get_nfts_by_account: SkillState
    opensea_create_listing: SkillState
    opensea_buy_nft: SkillState
    opensea_cancel_listing: SkillState
    opensea_update_listing: SkillState


_SKILL_NAME_TO_CLASS_MAP: dict[str, type[IntentKitSkill]] = {
    "opensea_get_collection": OpenSeaGetCollection,
    "opensea_get_collection_stats": OpenSeaGetCollectionStats,
    "opensea_get_nft": OpenSeaGetNft,
    "opensea_get_listings": OpenSeaGetListings,
    "opensea_get_offers": OpenSeaGetOffers,
    "opensea_get_events": OpenSeaGetEvents,
    "opensea_get_nfts_by_account": OpenSeaGetNftsByAccount,
    "opensea_create_listing": OpenSeaCreateListing,
    "opensea_buy_nft": OpenSeaBuyNft,
    "opensea_cancel_listing": OpenSeaCancelListing,
    "opensea_update_listing": OpenSeaUpdateListing,
}


class Config(SkillConfig):
    """Configuration for OpenSea skills."""

    enabled: bool
    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[IntentKitSkill]:
    """Get all OpenSea skills based on config states.

    Args:
        config: The configuration for OpenSea skills.
        is_private: Whether to include private skills.

    Returns:
        A list of OpenSea skills.
    """
    available_skills = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    logger.debug("Available OpenSea skills: %s", available_skills)

    result = []
    for name in available_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> IntentKitSkill | None:
    """Get an OpenSea skill by name, using cache."""
    if name in _cache:
        return _cache[name]

    skill_class = _SKILL_NAME_TO_CLASS_MAP.get(name)
    if not skill_class:
        logger.warning("Unknown OpenSea skill: %s", name)
        return None

    _cache[name] = skill_class()
    return _cache[name]


def available() -> bool:
    """Check if OpenSea skills are available (API key configured)."""
    return bool(system_config.opensea_api_key)
