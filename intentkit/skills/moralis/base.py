"""Base class for Wallet Portfolio tools."""

from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

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

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    # Optional fields for blockchain providers
    solana_networks: list[str] | None = Field(
        default=SOLANA_NETWORKS, description="Supported Solana networks"
    )

    def get_api_key(self) -> str:
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "platform":
            return config.moralis_api_key
        # for backward compatibility, may only have api_key in skill_config
        elif skill_config.get("api_key"):
            return skill_config.get("api_key")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}, or no api_key in config"
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
