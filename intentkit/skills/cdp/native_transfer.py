"""CDP native_transfer skill - Transfer native tokens."""

from decimal import Decimal

from pydantic import BaseModel, Field

from intentkit.skills.cdp.base import CDPBaseTool


class NativeTransferInput(BaseModel):
    """Input schema for native_transfer."""

    to: str = Field(..., description="The destination address to receive the funds")
    value: str = Field(
        ...,
        description="The amount to transfer in whole units (e.g. '0.1' for 0.1 ETH)",
    )


class CDPNativeTransfer(CDPBaseTool):
    """Transfer native tokens (ETH, MATIC, etc.) to another address.

    This tool transfers native tokens from the wallet to a destination address.
    """

    name: str = "cdp_native_transfer"
    description: str = """Transfer native tokens (ETH for EVM networks) from the wallet to another onchain address.

Inputs:
- to: The destination address to receive the funds
- value: The amount to transfer in whole units (e.g. '0.1' for 0.1 ETH)

Important notes:
- Ensure sufficient balance of the native asset before transferring
- Ensure there is sufficient balance for the transfer itself AND the gas cost of this transfer
"""
    args_schema: type[BaseModel] = NativeTransferInput

    async def _arun(
        self,
        to: str,
        value: str,
    ) -> str:
        """Transfer native tokens to a destination address.

        Args:
            to: The destination address.
            value: The amount to transfer in whole units (e.g., '0.1' for 0.1 ETH).

        Returns:
            A message containing the transfer details and transaction hash.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            # Convert value to Decimal
            value_decimal = Decimal(value)

            # Convert to wei (18 decimals)
            value_wei = int(value_decimal * Decimal(10**18))

            # Check balance before transfer
            balance_wei = await wallet.get_balance()

            if balance_wei < value_wei:
                balance_decimal = Decimal(balance_wei) / Decimal(10**18)
                return (
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
            await wallet.wait_for_transaction_receipt(tx_hash)

            return (
                f"Transferred {value} {native_symbol} to {to}\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error during transfer: {e!s}"
