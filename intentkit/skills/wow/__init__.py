"""WOW skills for Zora WOW ERC20 memecoin protocol on Base."""

from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.wow.base import WowBaseTool
from intentkit.skills.wow.buy_token import WowBuyToken
from intentkit.skills.wow.create_token import WowCreateToken
from intentkit.skills.wow.sell_token import WowSellToken


class SkillStates(TypedDict):
    wow_buy_token: SkillState
    wow_create_token: SkillState
    wow_sell_token: SkillState


class Config(SkillConfig):
    """Configuration for WOW skills."""

    states: SkillStates


# Legacy skill name mapping (old names -> new IntentKit names)
_LEGACY_NAME_MAP: dict[str, str] = {
    "WowActionProvider_buy_token": "wow_buy_token",
    "WowActionProvider_create_token": "wow_create_token",
    "WowActionProvider_sell_token": "wow_sell_token",
}

# Skill registry
_SKILLS: dict[str, type[WowBaseTool]] = {
    "wow_buy_token": WowBuyToken,
    "wow_create_token": WowCreateToken,
    "wow_sell_token": WowSellToken,
}

# Cache for skill instances
_cache: dict[str, WowBaseTool] = {}


def _normalize_skill_name(name: str) -> str:
    """Normalize legacy skill names to new names."""
    return _LEGACY_NAME_MAP.get(name, name)


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[WowBaseTool]:
    """Get all enabled WOW skills.

    Args:
        config: The configuration for WOW skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled WOW skills.
    """
    tools: list[WowBaseTool] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            # Normalize legacy skill names
            normalized_name = _normalize_skill_name(skill_name)
            # Check cache first
            if normalized_name in _cache:
                tools.append(_cache[normalized_name])
            else:
                skill_class = _SKILLS.get(normalized_name)
                if skill_class:
                    skill_instance = skill_class()
                    _cache[normalized_name] = skill_instance
                    tools.append(skill_instance)

    return tools


def available() -> bool:
    """Check if this skill category is available based on system config.

    WOW skills require an on-chain capable wallet (CDP or Safe/Privy).
    """
    # WOW works with any on-chain capable wallet
    # Check if we have at least CDP credentials configured
    has_cdp = all(
        [
            bool(system_config.cdp_api_key_id),
            bool(system_config.cdp_api_key_secret),
            bool(system_config.cdp_wallet_secret),
        ]
    )
    # Or Privy credentials
    has_privy = bool(system_config.privy_app_id) and bool(
        system_config.privy_app_secret
    )

    return has_cdp or has_privy
