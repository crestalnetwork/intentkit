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


# Cache for skill instances
_cache: dict[str, ERC721BaseTool] = {}


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
            # Check cache first
            if skill_name in _cache:
                tools.append(_cache[skill_name])
            else:
                skill_class = _SKILLS.get(skill_name)
                if skill_class:
                    skill_instance = skill_class()
                    _cache[skill_name] = skill_instance
                    tools.append(skill_instance)

    return tools


def available() -> bool:
    """Check if this skill category is available based on system config.

    ERC721 skills are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
