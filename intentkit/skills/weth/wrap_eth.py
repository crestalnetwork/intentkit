"""WETH wrap_eth skill - Wrap ETH to WETH."""

from decimal import Decimal

from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.weth.base import WethBaseTool
from intentkit.skills.weth.constants import WETH_ABI, get_weth_address


class WrapEthInput(BaseModel):
    """Input schema for wrap_eth."""

    amount_to_wrap: str = Field(
        ...,
        description="Amount of ETH to wrap in human-readable format (e.g., '0.1' for 0.1 ETH)",
    )


class WETHWrapEth(WethBaseTool):
    """Wrap ETH to WETH.

    This tool wraps native ETH to WETH (Wrapped ETH), which is an ERC20 token.
    WETH is useful for interacting with DeFi protocols that require ERC20 tokens.
    """

    name: str = "weth_wrap_eth"
    description: str = """Wrap ETH to WETH (Wrapped ETH).

Inputs:
- amount_to_wrap: Amount of ETH to wrap in human-readable format (e.g., '0.1' for 0.1 ETH)

WETH is an ERC20 token representation of ETH, useful for DeFi protocols that require ERC20 tokens.
The conversion rate is always 1:1 (1 ETH = 1 WETH).

Important notes:
- Ensure sufficient ETH balance before wrapping
- Some ETH will be needed for gas fees in addition to the amount being wrapped
"""
    args_schema: type[BaseModel] = WrapEthInput

    async def _arun(
        self,
        amount_to_wrap: str,
    ) -> str:
        """Wrap ETH to WETH.

        Args:
            amount_to_wrap: Amount of ETH to wrap in human-readable format.

        Returns:
            A message containing the wrap result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()
            network_id = wallet.network_id

            # Get WETH address for this network
            weth_address = get_weth_address(network_id)
            if not weth_address:
                return f"Error: WETH not supported on network {network_id}"

            # Convert human-readable ETH amount to wei (ETH has 18 decimals)
            amount_decimal = Decimal(amount_to_wrap)
            amount_in_wei = int(amount_decimal * Decimal(10**18))

            # Check ETH balance before wrapping
            eth_balance = await wallet.get_balance()

            if eth_balance < amount_in_wei:
                eth_balance_formatted = Decimal(eth_balance) / Decimal(10**18)
                return (
                    f"Error: Insufficient ETH balance. "
                    f"Requested to wrap {amount_to_wrap} ETH, "
                    f"but only {eth_balance_formatted} ETH is available. "
                    "Note: You also need additional ETH for gas fees."
                )

            w3 = Web3()
            checksum_weth = w3.to_checksum_address(weth_address)

            # Encode deposit function (no args, just send ETH)
            contract = w3.eth.contract(address=checksum_weth, abi=WETH_ABI)
            data = contract.encode_abi("deposit", [])

            # Send transaction with value
            tx_hash = await wallet.send_transaction(
                to=checksum_weth,
                value=amount_in_wei,
                data=data,
            )

            # Wait for receipt
            await wallet.wait_for_transaction_receipt(tx_hash)

            return f"Wrapped {amount_to_wrap} ETH to WETH.\nTransaction hash: {tx_hash}"

        except Exception as e:
            return f"Error wrapping ETH: {e!s}"
