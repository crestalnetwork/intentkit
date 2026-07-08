"""CDP get_wallet_details tool - Get wallet details."""

from decimal import Decimal
from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.cdp.base import CDPBaseTool
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION
from intentkit.wallets.web3 import get_async_web3_client


class GetWalletDetailsInput(BaseModel):
    """Input schema for get_wallet_details."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)


class CDPGetWalletDetails(CDPBaseTool):
    """Get details about a wallet.

    This tool returns comprehensive information about the selected wallet
    including address, network information, and native token balance.
    """

    name: str = "cdp_get_wallet_details"
    title: str = "Get Wallet Details"
    description: str = (
        "Get wallet details including address, network, balance, and provider type."
    )
    args_schema: ArgsSchema | None = GetWalletDetailsInput

    @override
    async def _arun(self, wallet_address: str) -> str:
        """Get details about the selected wallet.

        Returns:
            A formatted string containing wallet details and network information.
        """
        try:
            # Read-only: validate team ownership and the CDP provider.
            wallet = await self.ensure_cdp_provider(wallet_address)
            network_id = wallet.network

            # Read balance and chain id directly from the chain (no signing)
            w3 = get_async_web3_client(network_id)
            checksum_address = Web3.to_checksum_address(wallet_address)
            balance_wei = await w3.eth.get_balance(checksum_address)
            chain_id = await w3.eth.chain_id

            # Convert to human-readable format (18 decimals for ETH-like tokens)
            balance_decimal = Decimal(balance_wei) / Decimal(10**18)
            formatted_balance = f"{balance_decimal:.18f}".rstrip("0").rstrip(".")

            # Determine the native token symbol based on network
            network_info = {
                "ethereum-mainnet": {"symbol": "ETH", "display": "Ethereum Mainnet"},
                "base-mainnet": {"symbol": "ETH", "display": "Base Mainnet"},
                "base-sepolia": {"symbol": "ETH", "display": "Base Sepolia"},
                "polygon-mainnet": {"symbol": "MATIC", "display": "Polygon Mainnet"},
                "arbitrum-mainnet": {"symbol": "ETH", "display": "Arbitrum One"},
                "optimism-mainnet": {"symbol": "ETH", "display": "Optimism Mainnet"},
                "bnb-mainnet": {"symbol": "BNB", "display": "BNB Chain"},
            }
            info = network_info.get(
                network_id, {"symbol": "ETH", "display": network_id}
            )
            native_symbol = info["symbol"]
            network_display = info["display"]

            return f"""Wallet Details:
- Provider: CDP (Coinbase Developer Platform)
- Address: {checksum_address}
- Network:
  * Name: {network_display}
  * Network ID: {network_id}
  * Chain ID: {chain_id}
- Native Balance: {balance_wei} wei
- Native Balance: {formatted_balance} {native_symbol}"""

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Error getting wallet details: {e!s}")
