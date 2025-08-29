from typing import Dict, Literal

from intentkit.skills.base import IntentKitSkill


class XmtpBaseTool(IntentKitSkill):
    """Base class for XMTP-related skills."""

    # Set response format to content_and_artifact for returning tuple
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    # ChainId mapping for XMTP wallet_sendCalls (mainnet only)
    CHAIN_ID_HEX_BY_NETWORK: Dict[str, str] = {
        "ethereum-mainnet": "0x1",  # 1
        "base-mainnet": "0x2105",  # 8453
        "arbitrum-mainnet": "0xA4B1",  # 42161
        "optimism-mainnet": "0xA",  # 10
    }

    # CDP network mapping for swap quote API (mainnet only)
    NETWORK_FOR_CDP_MAPPING: Dict[str, str] = {
        "ethereum-mainnet": "ethereum",
        "base-mainnet": "base",
        "arbitrum-mainnet": "arbitrum",
        "optimism-mainnet": "optimism",
    }

    @property
    def category(self) -> str:
        """Return the skill category."""
        return "xmtp"

    def validate_network_and_get_chain_id(
        self, network_id: str, skill_name: str
    ) -> str:
        """Validate network and return chain ID hex.

        Args:
            network_id: The network ID to validate
            skill_name: The name of the skill for error messages

        Returns:
            The hex chain ID for the network

        Raises:
            ValueError: If the network is not supported
        """
        if network_id not in self.CHAIN_ID_HEX_BY_NETWORK:
            supported_networks = ", ".join(self.CHAIN_ID_HEX_BY_NETWORK.keys())
            raise ValueError(
                f"XMTP {skill_name} supports the following networks: {supported_networks}. "
                f"Current agent network: {network_id}"
            )
        return self.CHAIN_ID_HEX_BY_NETWORK[network_id]

    def get_cdp_network(self, network_id: str) -> str:
        """Get CDP network name for the given network ID.

        Args:
            network_id: The network ID

        Returns:
            The CDP network name

        Raises:
            ValueError: If the network is not supported for CDP
        """
        if network_id not in self.NETWORK_FOR_CDP_MAPPING:
            supported_networks = ", ".join(self.NETWORK_FOR_CDP_MAPPING.keys())
            raise ValueError(
                f"CDP swap does not support network: {network_id}. "
                f"Supported networks: {supported_networks}"
            )
        return self.NETWORK_FOR_CDP_MAPPING[network_id]
