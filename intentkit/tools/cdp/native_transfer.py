"""CDP native_transfer tool - Transfer native tokens."""

from decimal import Decimal
from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cdp.base import CDPBaseTool
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION


class NativeTransferInput(BaseModel):
    """Input schema for native_transfer."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)
    to: str = Field(..., description="Destination address")
    value: str = Field(
        ...,
        description="Amount in whole units (e.g. '0.1' for 0.1 ETH)",
    )


class CDPNativeTransfer(CDPBaseTool):
    """Transfer native tokens (ETH, MATIC, etc.) to another address.

    This tool transfers native tokens from the wallet to a destination address.
    """

    name: str = "cdp_native_transfer"
    description: str = "Transfer native tokens (ETH, MATIC, etc.) to another address. Ensure sufficient balance for transfer and gas."
    args_schema: ArgsSchema | None = NativeTransferInput

    @override
    async def _arun(
        self,
        wallet_address: str,
        to: str,
        value: str,
    ) -> str:
        """Transfer native tokens to a destination address.

        Args:
            wallet_address: The team wallet address to send from.
            to: The destination address.
            value: The amount to transfer in whole units (e.g., '0.1' for 0.1 ETH).

        Returns:
            A message containing the transfer details and transaction hash.
        """
        try:
            # Ensure the wallet provider is CDP
            await self.ensure_cdp_provider(wallet_address)

            # Get the unified wallet (signing-capable, guarded)
            wallet = await self.get_unified_wallet(wallet_address)

            # Convert value to Decimal
            value_decimal = Decimal(value)

            # Convert to wei (18 decimals)
            value_wei = int(value_decimal * Decimal(10**18))

            # Check balance before transfer
            balance_wei = await wallet.get_balance()

            if balance_wei < value_wei:
                balance_decimal = Decimal(balance_wei) / Decimal(10**18)
                raise ToolException(
                    f"Error: Insufficient balance. "
                    f"Requested to send {value}, but only {balance_decimal} is available. "
                    "Note: You also need additional funds for gas fees."
                )

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

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=to,
                value=value_wei,
            )

            # Wait for receipt
            await wallet.wait_for_receipt(tx_hash)

            return (
                f"Transferred {value} {native_symbol} to {to}\n"
                f"Transaction hash: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Error during transfer: {e!s}")
