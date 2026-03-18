"""Base class for Wallet Portfolio tools."""

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill

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

    def get_api_key(self) -> str:
        if not config.moralis_api_key:
            raise ToolException("Moralis API key is not configured")
        return config.moralis_api_key

    category: str = "moralis"

    def _get_chain_name(self, chain_id: int) -> str:
        """Convert chain ID to chain name for API calls.

        Args:
            chain_id: The blockchain network ID

        Returns:
            The chain name used by the API
        """
        return CHAIN_MAPPING.get(chain_id, "eth")
