"""Aave V3 tools base class."""

from langchain_core.tools.base import ToolException

from intentkit.tools.aave_v3.constants import NETWORK_TO_CHAIN_ID
from intentkit.tools.onchain import IntentKitOnChainTool


class AaveV3BaseTool(IntentKitOnChainTool):
    """Base class for Aave V3 lending protocol tools."""

    category: str = "aave_v3"

    def _resolve_chain_id(self, network_id: str) -> int:
        """Map a network to its Aave V3 chain ID.

        Raises:
            ToolException: If Aave V3 is not supported on the network.
        """
        chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
        if not chain_id:
            supported = ", ".join(NETWORK_TO_CHAIN_ID.keys())
            raise ToolException(
                f"Aave V3 is not supported on {network_id}. "
                f"Supported networks: {supported}"
            )
        return chain_id
