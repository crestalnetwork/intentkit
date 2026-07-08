from langchain_core.tools.base import ToolException

from intentkit.tools.aerodrome.constants import NETWORK_TO_CHAIN_ID
from intentkit.tools.onchain import IntentKitOnChainTool


class AerodromeBaseTool(IntentKitOnChainTool):
    """Base class for Aerodrome tools."""

    category: str = "aerodrome"

    def _resolve_chain_id(self, network_id: str) -> int:
        """Map a network to its Aerodrome chain ID.

        Raises:
            ToolException: If Aerodrome is not supported on the network.
        """
        chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
        if not chain_id:
            raise ToolException(
                f"Aerodrome is only supported on Base. Wallet network: {network_id}"
            )
        return chain_id
