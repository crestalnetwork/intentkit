"""CDP get_balance skill - Get native token balance."""

from decimal import Decimal
from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel

from intentkit.skills.cdp.base import CDPBaseTool


class GetBalanceInput(BaseModel):
    """Input schema for get_balance. No inputs required."""

    pass


class CDPGetBalance(CDPBaseTool):
    """Get the native token balance of the connected wallet.

    This tool returns the native token balance (ETH, MATIC, etc.)
    of the wallet in both wei and human-readable format.
    """

    name: str = "cdp_get_balance"
    description: str = "Get the native token balance (ETH, MATIC, etc.) of the connected wallet. No inputs required."
    args_schema: ArgsSchema | None = GetBalanceInput

    @override
    async def _arun(self) -> str:
        """Get the native currency balance for the connected wallet.

        Returns:
            A message containing the wallet address and balance information.
        """
        try:
            # Ensure the wallet provider is CDP
            self.ensure_cdp_provider()

            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            # Get balance in wei
            balance_wei = await wallet.get_balance()

            # Convert to human-readable format (18 decimals for ETH-like tokens)
            balance_decimal = Decimal(balance_wei) / Decimal(10**18)
            formatted_balance = f"{balance_decimal:.18f}".rstrip("0").rstrip(".")

            # Determine the native token symbol based on network
            network_id = wallet.network_id
            native_symbols = {
                "ethereum-mainnet": "ETH",
                "base-mainnet": "ETH",
                "base-sepolia": "ETH",
                "polygon-mainnet": "MATIC",
                "arbitrum-mainnet": "ETH",
                "optimism-mainnet": "ETH",
                "bnb-mainnet": "BNB",
            }
            native_symbol = native_symbols.get(network_id, "ETH")

            return (
                f"Native balance at address {wallet.address}:\n"
                f"- {balance_wei} wei\n"
                f"- {formatted_balance} {native_symbol}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Error getting balance: {e!s}")
