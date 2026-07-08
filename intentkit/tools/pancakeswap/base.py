from langchain_core.tools.base import ToolException

from intentkit.tools.onchain import IntentKitOnChainTool
from intentkit.tools.pancakeswap.constants import NETWORK_TO_CHAIN_ID


class PancakeSwapBaseTool(IntentKitOnChainTool):
    """Base class for PancakeSwap tools."""

    category: str = "pancakeswap"

    def _resolve_chain_id(self, network_id: str) -> int:
        """Map a network to its PancakeSwap chain ID.

        Raises:
            ToolException: If PancakeSwap is not supported on the network.
        """
        chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
        if not chain_id:
            raise ToolException(
                f"PancakeSwap not supported on wallet network {network_id}. "
                f"Supported: {', '.join(NETWORK_TO_CHAIN_ID.keys())}"
            )
        return chain_id
