"""ERC20 transfer tool."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.erc20.base import ERC20BaseTool
from intentkit.tools.erc20.constants import ERC20_ABI
from intentkit.tools.erc20.utils import get_token_details
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION


class TransferInput(BaseModel):
    """Input schema for ERC20 transfer."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)
    contract_address: str = Field(..., description="ERC20 token contract address")
    destination_address: str = Field(..., description="Recipient address")
    amount: str = Field(
        ...,
        description="Amount in whole units (e.g. '10.5' for 10.5 USDC)",
    )


class ERC20Transfer(ERC20BaseTool):
    """Transfer ERC20 tokens to another address.

    This tool transfers ERC20 tokens from the wallet to a destination address.
    """

    name: str = "erc20_transfer"
    title: str = "Transfer ERC20"
    description: str = "Transfer ERC20 tokens to another address. Use erc20_get_token_address first if only a symbol is provided. Ensure sufficient balance for transfer and gas."
    args_schema: ArgsSchema | None = TransferInput

    @override
    async def _arun(
        self,
        wallet_address: str,
        contract_address: str,
        destination_address: str,
        amount: str,
        **kwargs: Any,
    ) -> str:
        """Transfer ERC20 tokens to a destination address.

        Args:
            wallet_address: The team wallet address to send from.
            contract_address: The contract address of the ERC20 token.
            destination_address: The address to send the tokens to.
            amount: The amount to transfer in whole units.

        Returns:
            A message containing the transfer result or error details.
        """
        try:
            # Get the unified wallet (signing-capable, guarded)
            wallet = await self.get_unified_wallet(wallet_address)
            w3_read = self.web3_client()

            w3 = Web3()
            checksum_contract = w3.to_checksum_address(contract_address)
            checksum_destination = w3.to_checksum_address(destination_address)

            # Get token details
            token_details = await get_token_details(
                w3_read, contract_address, wallet.address
            )

            if not token_details:
                raise ToolException(
                    f"Error: Could not fetch token details for {contract_address}. "
                    "Please verify the token address is correct."
                )

            # Convert amount from whole units to atomic units
            amount_in_atomic_units = int(Decimal(amount) * (10**token_details.decimals))

            # Check token balance
            if token_details.balance < amount_in_atomic_units:
                raise ToolException(
                    f"Error: Insufficient {token_details.name} ({contract_address}) token balance. "
                    f"Requested to send {amount} of {token_details.name}, "
                    f"but only {token_details.formatted_balance} is available."
                )

            # Guardrails to prevent loss of funds
            if contract_address.lower() == destination_address.lower():
                raise ToolException(
                    "Error: Transfer destination is the token contract address. "
                    "Refusing transfer to prevent loss of funds."
                )

            # Check if destination is also an ERC20 token contract
            # This helps prevent accidental transfers to token contracts
            destination_token_details = await get_token_details(
                w3_read, destination_address, wallet.address
            )
            if destination_token_details:
                raise ToolException(
                    "Error: Transfer destination is an ERC20 token contract. "
                    "Refusing to transfer to prevent loss of funds."
                )

            # Encode transfer function
            contract = w3.eth.contract(address=checksum_contract, abi=ERC20_ABI)
            data = contract.encode_abi(
                "transfer", [checksum_destination, amount_in_atomic_units]
            )

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=checksum_contract,
                data=data,
            )

            # Wait for receipt
            _ = await wallet.wait_for_receipt(tx_hash)

            return (
                f"Transferred {amount} of {token_details.name} ({contract_address}) "
                f"to {destination_address}.\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            raise ToolException(f"Error transferring the asset: {e!s}")
