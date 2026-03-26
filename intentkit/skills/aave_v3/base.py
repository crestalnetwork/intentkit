"""Aave V3 skills base class."""

from langchain_core.tools.base import ToolException

from intentkit.skills.aave_v3.constants import NETWORK_TO_CHAIN_ID
from intentkit.skills.onchain import IntentKitOnChainSkill


class AaveV3BaseTool(IntentKitOnChainSkill):
    """Base class for Aave V3 lending protocol skills."""

    category: str = "aave_v3"

    def _resolve_chain_id(self) -> int:
        """Validate network and return chain ID.

        Raises:
            ToolException: If network is not configured or not supported.
        """
        network_id = self.get_agent_network_id()
        if not network_id:
            raise ToolException("Agent network_id is not configured")

        chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
        if not chain_id:
            supported = ", ".join(NETWORK_TO_CHAIN_ID.keys())
            raise ToolException(
                f"Aave V3 is not supported on {network_id}. "
                f"Supported networks: {supported}"
            )
        return chain_id
