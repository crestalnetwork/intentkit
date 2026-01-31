"""Basename skills for ENS-style domain registration on Base."""

from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.basename.base import BasenameBaseTool
from intentkit.skills.basename.register import BasenameRegister


class SkillStates(TypedDict):
    basename_register_basename: SkillState


class Config(SkillConfig):
    """Configuration for Basename skills."""

    states: SkillStates


# Legacy skill name mapping (legacy names -> IntentKit names)
_LEGACY_NAME_MAP: dict[str, str] = {
    "BasenameActionProvider_register_basename": "basename_register_basename",
}

# Skill registry
_SKILLS: dict[str, type[BasenameBaseTool]] = {
    "basename_register_basename": BasenameRegister,
}

# Cache for skill instances
_cache: dict[str, BasenameBaseTool] = {}


def _normalize_skill_name(name: str) -> str:
    """Normalize legacy skill names to new names."""
    return _LEGACY_NAME_MAP.get(name, name)


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[BasenameBaseTool]:
    """Get all enabled Basename skills.

    Args:
        config: The configuration for Basename skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled Basename skills.
    """
    tools: list[BasenameBaseTool] = []

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

    Basename skills require CDP credentials for wallet operations,
    or can work with Safe/Privy wallet providers.
    """
    # Basename works with any on-chain capable wallet
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
