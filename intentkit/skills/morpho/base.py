"""Morpho skills base class."""

from langchain_core.tools.base import ToolException
from web3 import AsyncWeb3, Web3

from intentkit.skills.morpho.constants import (
    MORPHO_BLUE_ABI,
    MORPHO_BLUE_ADDRESS,
    SUPPORTED_NETWORKS,
)
from intentkit.skills.onchain import IntentKitOnChainSkill


class MorphoBaseTool(IntentKitOnChainSkill):
    """Base class for Morpho lending protocol skills.

    Morpho skills provide functionality to interact with Morpho Vaults
    and Morpho Blue markets including depositing, withdrawing, borrowing,
    and repaying assets.

    These skills work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "morpho"

    def _validate_network(self, network_id: str) -> None:
        """Validate the network is supported by Morpho."""
        if network_id not in SUPPORTED_NETWORKS:
            raise ToolException(
                f"Error: Morpho is not supported on network {network_id}. "
                f"Supported networks: {', '.join(SUPPORTED_NETWORKS)}"
            )

    @staticmethod
    def _parse_market_id(market_id: str) -> bytes:
        """Convert market_id hex string to bytes32."""
        market_id_bytes = bytes.fromhex(market_id.replace("0x", ""))
        if len(market_id_bytes) != 32:
            raise ToolException(
                "Error: market_id must be a 32-byte hex string (bytes32)"
            )
        return market_id_bytes

    async def _get_market_params(
        self, w3: AsyncWeb3, market_id: str
    ) -> tuple[str, str, str, str, int]:
        """Fetch MarketParams from Morpho Blue by market ID.

        Returns checksummed addresses ready for ABI encoding:
            (loanToken, collateralToken, oracle, irm, lltv)
        """
        checksum_morpho = Web3.to_checksum_address(MORPHO_BLUE_ADDRESS)
        market_id_bytes = self._parse_market_id(market_id)

        morpho = w3.eth.contract(address=checksum_morpho, abi=MORPHO_BLUE_ABI)
        result = await morpho.functions.idToMarketParams(market_id_bytes).call()
        loan_token, collateral_token, oracle, irm, lltv = result

        if loan_token == "0x0000000000000000000000000000000000000000":
            raise ToolException(
                f"Error: Market {market_id} does not exist on Morpho Blue"
            )

        return (
            Web3.to_checksum_address(loan_token),
            Web3.to_checksum_address(collateral_token),
            Web3.to_checksum_address(oracle),
            Web3.to_checksum_address(irm),
            lltv,
        )
