"""
Base class for Enso tools with unified wallet provider support.

This module provides the EnsoBaseTool class which supports both
CDP and Privy wallet providers for Enso DeFi operations.
"""

from decimal import Decimal

from langchain_core.tools.base import ToolException

from intentkit.abstracts.graph import AgentContext
from intentkit.config.config import config
from intentkit.tools.onchain import IntentKitOnChainTool
from intentkit.utils.chain import (
    network_to_id,
    resolve_supported_network,
)

base_url = "https://api.enso.finance"


class EnsoBaseTool(IntentKitOnChainTool):
    """
    Base class for Enso tools.

    This class extends IntentKitOnChainTool to provide unified wallet
    provider support for Enso DeFi operations, automatically selecting
    the appropriate provider based on the agent's configuration
    (CDP or Privy).
    """

    def get_main_tokens(self, context: AgentContext) -> list[str]:
        """Per-agent main token configuration was removed; default to no extra tokens."""
        return []

    def get_api_token(self, context: AgentContext) -> str:
        if not config.enso_api_token:
            raise ToolException("Enso API token is not configured")
        return config.enso_api_token

    def resolve_chain_id(self, chain_id: int | None, network_id: str) -> int:
        """
        Resolve the chain ID for the operation.

        An explicit chain_id wins; otherwise the given network is mapped
        to its chain ID.

        Args:
            chain_id: Optional explicit chain ID.
            network_id: Network used when no explicit chain ID is given
                (a wallet's network, or the platform default).

        Returns:
            The resolved chain ID.

        Raises:
            ToolException: If the network is not supported.
        """
        if chain_id:
            return chain_id

        try:
            network = resolve_supported_network(network_id)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ToolException(f"Unsupported wallet network: {network_id}") from exc

        resolved_id = network_to_id.get(network)
        if resolved_id is None:
            raise ToolException(
                f"Unable to determine chain id for network: {network_id}"
            )
        return int(resolved_id)

    category: str = "enso"


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
