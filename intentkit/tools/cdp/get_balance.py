"""CDP get_balance tool - Get native token balance."""

from decimal import Decimal
from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.cdp.base import CDPBaseTool
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION
from intentkit.wallets.web3 import get_async_web3_client


class GetBalanceInput(BaseModel):
    """Input schema for get_balance."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)


class CDPGetBalance(CDPBaseTool):
    """Get the native token balance of a wallet.

    This tool returns the native token balance (ETH, MATIC, etc.)
    of the wallet in both wei and human-readable format.
    """

    name: str = "cdp_get_balance"
    title: str = "Get Balance"
    description: str = "Get the native token balance (ETH, MATIC, etc.)."
    args_schema: ArgsSchema | None = GetBalanceInput

    @override
    async def _arun(self, wallet_address: str) -> str:
        """Get the native currency balance for the selected wallet.

        Returns:
            A message containing the wallet address and balance information.
        """
        try:
            # Read-only: validate team ownership and the CDP provider.
            wallet = await self.ensure_cdp_provider(wallet_address)
            network_id = wallet.network

            # Read the balance directly from the chain (no signing needed)
            w3 = get_async_web3_client(network_id)
            checksum_address = Web3.to_checksum_address(wallet_address)
            balance_wei = await w3.eth.get_balance(checksum_address)

            # Convert to human-readable format (18 decimals for ETH-like tokens)
            balance_decimal = Decimal(balance_wei) / Decimal(10**18)
            formatted_balance = f"{balance_decimal:.18f}".rstrip("0").rstrip(".")

            # Determine the native token symbol based on network
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
                f"Native balance at address {checksum_address}:\n"
                f"- {balance_wei} wei\n"
                f"- {formatted_balance} {native_symbol}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Error getting balance: {e!s}")
