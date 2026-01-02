"""
Base class for Enso tools with unified wallet provider support.

This module provides the EnsoBaseTool class which supports both
CDP and Privy wallet providers for Enso DeFi operations.
"""

from decimal import Decimal
from typing import Any

from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.config.config import config
from intentkit.skills.onchain import IntentKitOnChainSkill
from intentkit.utils.chain import (
    ChainProvider,
    network_to_id,
    resolve_quicknode_network,
)

base_url = "https://api.enso.finance"


class EnsoBaseTool(IntentKitOnChainSkill):
    """
    Base class for Enso tools.

    This class extends IntentKitOnChainSkill to provide unified wallet
    provider support for Enso DeFi operations, automatically selecting
    the appropriate provider based on the agent's configuration
    (CDP or Privy).
    """

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    async def get_enso_wallet_provider(self, context: AgentContext) -> Any:
        """
        Get the wallet provider for Enso operations.

        This method uses the unified wallet provider from IntentKitOnChainSkill,
        which automatically selects:
        - CdpEvmWalletProvider for CDP wallets
        - SafeWalletProvider for Privy wallets

        Args:
            context: The skill context containing agent information.

        Returns:
            The wallet provider instance.
        """
        # Use the unified method from parent class
        return await self.get_wallet_provider()

    async def get_enso_wallet_address(self, context: AgentContext) -> str:
        """
        Get the wallet address for Enso operations.

        This method handles both CDP (sync) and Privy (async) providers.

        Args:
            context: The skill context containing agent information.

        Returns:
            The wallet address as a checksummed hex string.
        """
        # Use the unified method from parent class
        return await self.get_wallet_address()

    def get_chain_provider(self, context: AgentContext) -> ChainProvider | None:
        """Get the chain provider configuration."""
        return config.chain_provider

    def get_main_tokens(self, context: AgentContext) -> list[str]:
        """Get the main tokens configured for this skill."""
        skill_config = context.agent.skill_config(self.category)
        if "main_tokens" in skill_config and skill_config["main_tokens"]:
            return skill_config["main_tokens"]
        return []

    def get_api_token(self, context: AgentContext) -> str:
        """
        Get the Enso API token.

        Args:
            context: The skill context containing agent information.

        Returns:
            The API token string.

        Raises:
            ToolException: If no valid API token is configured.
        """
        skill_config = context.agent.skill_config(self.category)
        api_key_provider = skill_config.get("api_key_provider")
        if api_key_provider == "platform":
            return config.enso_api_token
        # for backward compatibility, may only have api_token in skill_config
        elif skill_config.get("api_token"):
            return skill_config.get("api_token")
        else:
            raise ToolException(
                f"Invalid API key provider: {api_key_provider}, or no api_token in config"
            )

    def resolve_chain_id(
        self, context: AgentContext, chain_id: int | None = None
    ) -> int:
        """
        Resolve the chain ID for the operation.

        Args:
            context: The skill context containing agent information.
            chain_id: Optional explicit chain ID.

        Returns:
            The resolved chain ID.

        Raises:
            ToolException: If the network is not supported.
        """
        if chain_id:
            return chain_id

        agent = context.agent
        try:
            network = resolve_quicknode_network(agent.network_id)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ToolException(
                f"Unsupported network configured for agent: {agent.network_id}"
            ) from exc

        network_id = network_to_id.get(network)
        if network_id is None:
            raise ToolException(
                f"Unable to determine chain id for network: {agent.network_id}"
            )
        return int(network_id)

    @property
    def category(self) -> str:
        return "enso"


def format_amount_with_decimals(amount: object, decimals: int | None) -> str | None:
    """
    Format a token amount with the correct number of decimals.

    Args:
        amount: The raw token amount.
        decimals: The number of decimals for the token.

    Returns:
        The formatted amount as a string, or None if formatting fails.
    """
    if amount is None or decimals is None:
        return None

    try:
        value = Decimal(str(amount)) / (Decimal(10) ** decimals)
        return format(value, "f")
    except Exception:  # pragma: no cover - defensive
        return None
