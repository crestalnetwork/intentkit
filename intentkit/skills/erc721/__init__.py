"""ERC721 NFT skills."""

from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.erc721.base import ERC721BaseTool
from intentkit.skills.erc721.get_balance import ERC721GetBalance
from intentkit.skills.erc721.mint import ERC721Mint
from intentkit.skills.erc721.transfer import ERC721Transfer


class SkillStates(TypedDict):
    erc721_get_balance: SkillState
    erc721_mint: SkillState
    erc721_transfer: SkillState


class Config(SkillConfig):
    """Configuration for ERC721 skills."""

    states: SkillStates


# Skill registry
_SKILLS: dict[str, type[ERC721BaseTool]] = {
    "erc721_get_balance": ERC721GetBalance,
    "erc721_mint": ERC721Mint,
    "erc721_transfer": ERC721Transfer,
}

# Legacy skill name mapping (legacy names -> IntentKit names)
_LEGACY_NAME_MAP: dict[str, str] = {
    "Erc721ActionProvider_get_balance": "erc721_get_balance",
    "Erc721ActionProvider_mint": "erc721_mint",
    "Erc721ActionProvider_transfer": "erc721_transfer",
}

# Cache for skill instances
_cache: dict[str, ERC721BaseTool] = {}


def _normalize_skill_name(name: str) -> str:
    """Normalize legacy skill names to new names."""
    return _LEGACY_NAME_MAP.get(name, name)


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[ERC721BaseTool]:
    """Get all enabled ERC721 skills.

    Args:
        config: The configuration for ERC721 skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled ERC721 skills.
    """
    tools: list[ERC721BaseTool] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            # Normalize legacy names to new names
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

    ERC721 skills are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
