"""Wallet Portfolio Skills for IntentKit."""

import logging
from typing import Dict, List, NotRequired, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.moralis.base import WalletBaseTool
from skills.moralis.fetch_blockchain_data import (
    FetchBlockByDate,
    FetchBlockByHashOrNumber,
    FetchLatestBlock,
)
from skills.moralis.fetch_blockchain_transaction import FetchTransactionByHash
from skills.moralis.fetch_chain_portfolio import FetchChainPortfolio
from skills.moralis.fetch_nft_portfolio import FetchNftPortfolio
from skills.moralis.fetch_solana_portfolio import FetchSolanaPortfolio
from skills.moralis.fetch_transaction_history import FetchTransactionHistory
from skills.moralis.fetch_wallet_portfolio import FetchWalletPortfolio

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    """Configuration of states for wallet skills."""

    fetch_wallet_portfolio: SkillState
    fetch_chain_portfolio: SkillState
    fetch_nft_portfolio: SkillState
    fetch_transaction_history: SkillState
    fetch_solana_portfolio: SkillState
    fetch_transaction_by_hash: SkillState
    fetch_latest_block: SkillState
    fetch_block_by_hash_or_number: SkillState
    fetch_block_by_date: SkillState


class Config(SkillConfig):
    """Configuration for Wallet Portfolio skills."""

    api_key: str
    states: SkillStates
    supported_chains: NotRequired[Dict[str, bool]] = {"evm": True, "solana": True}


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> List[WalletBaseTool]:
    """Get all Wallet Portfolio skills.

    Args:
        config: Skill configuration
        is_private: Whether the request is from an authenticated user
        store: Skill store for persistence
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
    # api key
    if config.get("api_key_provider") == "agent_owner":
        api_key = config.get("api_key")
    else:
        api_key = store.get_system_config("moralis_api_key")

    # Get each skill using the getter
    result = []
    for name in available_skills:
        skill = get_wallet_skill(name, api_key, store)
        if skill:
            result.append(skill)
    return result


def get_wallet_skill(
    name: str,
    api_key: str,
    store: SkillStoreABC,
) -> WalletBaseTool:
    """Get a specific Wallet Portfolio skill by name.

    Args:
        name: Name of the skill to get
        api_key: API key for Moralis
        store: Skill store for persistence

    Returns:
        The requested skill
    """
    skill_classes = {
        "fetch_wallet_portfolio": FetchWalletPortfolio,
        "fetch_chain_portfolio": FetchChainPortfolio,
        "fetch_nft_portfolio": FetchNftPortfolio,
        "fetch_transaction_history": FetchTransactionHistory,
        "fetch_solana_portfolio": FetchSolanaPortfolio,
        "fetch_transaction_by_hash": FetchTransactionByHash,
        "fetch_latest_block": FetchLatestBlock,
        "fetch_block_by_hash_or_number": FetchBlockByHashOrNumber,
        "fetch_block_by_date": FetchBlockByDate,
    }

    if name not in skill_classes:
        logger.warning(f"Unknown Wallet Portfolio skill: {name}")
        return None

    return skill_classes[name](
        api_key=api_key,
        skill_store=store,
    )
