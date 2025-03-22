"""Base class for Wallet Portfolio tools."""

from typing import Type, Optional, Dict, List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill


# Chain ID to chain name mapping for EVM chains
CHAIN_MAPPING = {
    1: "eth",
    56: "bsc",
    137: "polygon",
    42161: "arbitrum",
    10: "optimism",
    43114: "avalanche",
    250: "fantom",
    8453: "base",
}

# Solana networks
SOLANA_NETWORKS = ["mainnet", "devnet"]


class WalletBaseTool(IntentKitSkill):
    """Base class for all wallet portfolio tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )
    api_key: str = Field(description="API key for the wallet data provider")
    agent_id: str = Field(description="ID of the agent using this skill")
    
    # Optional fields for blockchain providers
    solana_networks: Optional[List[str]] = Field(
        default=SOLANA_NETWORKS,
        description="Supported Solana networks"
    )
    
    @property
    def category(self) -> str:
        return "moralis"
    
    def _get_chain_name(self, chain_id: int) -> str:
        """Convert chain ID to chain name for API calls.
        
        Args:
            chain_id: The blockchain network ID
            
        Returns:
            The chain name used by the API
        """
        return CHAIN_MAPPING.get(chain_id, "eth")