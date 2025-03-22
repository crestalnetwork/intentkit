"""Wallet Portfolio Skills for IntentKit."""

from typing import Dict, List, Optional, TypedDict, Union, Any, NotRequired

from abstracts.agent import AgentStoreABC
from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.wallet.base import WalletBaseTool
from skills.wallet.moralis_fetch_wallet_portfolio import FetchWalletPortfolio
from skills.wallet.moralis_fetch_chain_portfolio import FetchChainPortfolio
from skills.wallet.moralis_fetch_nft_portfolio import FetchNftPortfolio
from skills.wallet.moralis_fetch_transaction_history import FetchTransactionHistory
from skills.wallet.moralis_fetch_solana_portfolio import FetchSolanaPortfolio

# Define skill state configuration
class SkillStates(TypedDict):
    """Configuration of states for wallet skills."""
    
    moralis_fetch_wallet_portfolio: SkillState
    moralis_fetch_chain_portfolio: SkillState
    moralis_fetch_nft_portfolio: SkillState
    moralis_fetch_transaction_history: SkillState
    moralis_etch_solana_portfolio: SkillState


class Config(SkillConfig):
    """Configuration for Wallet Portfolio skills."""
    
    api_key: str
    states: SkillStates
    supported_chains: NotRequired[Dict[str, bool]] = {"evm": True, "solana": True}


def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    agent_id: str,
    agent_store: AgentStoreABC,
    chain_provider: Any = None,
    **_,
) -> List[WalletBaseTool]:
    """Get all Wallet Portfolio skills.
    
    Args:
        config: Skill configuration
        is_private: Whether the request is from an authenticated user
        store: Skill store for persistence
        agent_id: ID of the agent
        agent_store: Agent store for persistence
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
            if skill_name == "fetch_solana_portfolio" and not config.get("supported_chains", {}).get("solana", True):
                continue
                
            available_skills.append(skill_name)

    # Get each skill using the getter
    return [
        get_wallet_skill(
            name, 
            config["api_key"], 
            store, 
            agent_id, 
            agent_store,
            chain_provider
        ) 
        for name in available_skills
    ]


def get_wallet_skill(
    name: str,
    api_key: str,
    store: SkillStoreABC,
    agent_id: str,
    agent_store: AgentStoreABC,
    chain_provider: Any = None,
) -> WalletBaseTool:
    """Get a specific Wallet Portfolio skill by name.
    
    Args:
        name: Name of the skill to get
        api_key: API key for the data provider
        store: Skill store for persistence
        agent_id: ID of the agent
        agent_store: Agent store for persistence
        chain_provider: Optional chain provider for blockchain interactions
        
    Returns:
        The requested skill
        
    Raises:
        ValueError: If the skill name is unknown
    """
    skill_classes = {
        "fetch_wallet_portfolio": FetchWalletPortfolio,
        "fetch_chain_portfolio": FetchChainPortfolio,
        "fetch_nft_portfolio": FetchNftPortfolio,
        "fetch_transaction_history": FetchTransactionHistory,
        "fetch_solana_portfolio": FetchSolanaPortfolio,
    }
    
    if name not in skill_classes:
        raise ValueError(f"Unknown Wallet Portfolio skill: {name}")
    
    return skill_classes[name](
        api_key=api_key,
        skill_store=store,
        agent_id=agent_id
    )