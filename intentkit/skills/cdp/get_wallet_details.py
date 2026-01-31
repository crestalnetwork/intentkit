"""CDP get_wallet_details skill - Get connected wallet details."""

from decimal import Decimal

from pydantic import BaseModel

from intentkit.skills.cdp.base import CDPBaseTool


class GetWalletDetailsInput(BaseModel):
    """Input schema for get_wallet_details. No inputs required."""

    pass


class CDPGetWalletDetails(CDPBaseTool):
    """Get details about the connected wallet.

    This tool returns comprehensive information about the connected wallet
    including address, network information, and native token balance.
    """

    name: str = "cdp_get_wallet_details"
    description: str = """Get details about the connected wallet.

Returns wallet details including:
- Wallet address
- Network information (network ID, chain ID)
- Native token balance (in wei and human-readable format)
- Wallet provider type

No inputs required.
"""
    args_schema: type[BaseModel] = GetWalletDetailsInput

    async def _arun(self) -> str:
        """Get details about the connected wallet.

        Returns:
            A formatted string containing wallet details and network information.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            # Get balance in wei
            balance_wei = await wallet.get_balance()

            # Convert to human-readable format (18 decimals for ETH-like tokens)
            balance_decimal = Decimal(balance_wei) / Decimal(10**18)
            formatted_balance = f"{balance_decimal:.18f}".rstrip("0").rstrip(".")

            # Determine the native token symbol based on network
            network_id = wallet.network_id
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

            # Determine provider type
            if wallet.is_cdp_provider():
                provider_name = "CDP (Coinbase Developer Platform)"
            elif wallet.is_safe_provider():
                provider_name = "Safe (Smart Account)"
            else:
                provider_name = "Unknown"

            return f"""Wallet Details:
- Provider: {provider_name}
- Address: {wallet.address}
- Network:
  * Name: {network_display}
  * Network ID: {network_id}
  * Chain ID: {wallet.chain_id or "N/A"}
- Native Balance: {balance_wei} wei
- Native Balance: {formatted_balance} {native_symbol}"""

        except Exception as e:
            return f"Error getting wallet details: {e!s}"
