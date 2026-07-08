from langchain_core.tools.base import ToolException

from intentkit.tools.onchain import IntentKitOnChainTool
from intentkit.tools.uniswap.constants import NETWORK_TO_CHAIN_ID


class UniswapBaseTool(IntentKitOnChainTool):
    """Base class for Uniswap tools."""

    category: str = "uniswap"

    def _resolve_chain_id(self, network_id: str) -> int:
        """Map a network to its Uniswap chain ID.

        Raises:
            ToolException: If Uniswap is not supported on the network.
        """
        chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
        if not chain_id:
            raise ToolException(
                f"Uniswap not supported on wallet network {network_id}. "
                f"Supported: {', '.join(NETWORK_TO_CHAIN_ID.keys())}"
            )
        return chain_id
