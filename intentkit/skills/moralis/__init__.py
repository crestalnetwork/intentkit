"""Wallet Portfolio Skills for IntentKit."""

import logging
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.moralis.base import WalletBaseTool
from intentkit.skills.moralis.fetch_chain_portfolio import FetchChainPortfolio
from intentkit.skills.moralis.fetch_nft_portfolio import FetchNftPortfolio
from intentkit.skills.moralis.fetch_solana_portfolio import FetchSolanaPortfolio
from intentkit.skills.moralis.fetch_wallet_portfolio import FetchWalletPortfolio

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    """Configuration of states for wallet skills."""

    fetch_wallet_portfolio: SkillState
    fetch_chain_portfolio: SkillState
    fetch_nft_portfolio: SkillState
    fetch_solana_portfolio: SkillState


class Config(SkillConfig):
    """Configuration for Wallet Portfolio skills."""

    states: SkillStates
    supported_chains: dict[str, bool]


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[WalletBaseTool]:
    """Get all Wallet Portfolio skills.

    Args:
        config: Skill configuration
        is_private: Whether the request is from an authenticated user
        chain_provider: Optional chain provider for blockchain interactions
        **_: Additional arguments

    Returns:
        List of enabled wallet skills
    """
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            # Check chain support for Solana-specific skills
            if skill_name == "fetch_solana_portfolio" and not config.get(
                "supported_chains", {}
            ).get("solana", True):
                continue

            available_skills.append(skill_name)

    # Get each skill using the getter
    result = []
    for name in available_skills:
        skill = get_wallet_skill(name)
        if skill:
            result.append(skill)
    return result


def get_wallet_skill(
    name: str,
) -> WalletBaseTool:
    """Get a specific Wallet Portfolio skill by name.

    Args:
        name: Name of the skill to get

    Returns:
        The requested skill
    """
    skill_classes = {
        "fetch_wallet_portfolio": FetchWalletPortfolio,
        "fetch_chain_portfolio": FetchChainPortfolio,
        "fetch_nft_portfolio": FetchNftPortfolio,
        "fetch_solana_portfolio": FetchSolanaPortfolio,
    }

    if name not in skill_classes:
        logger.warning("Unknown Wallet Portfolio skill: %s", name)
        return None

    return skill_classes[name]()


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return bool(system_config.moralis_api_key)
