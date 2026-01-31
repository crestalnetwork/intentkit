"""ERC20 transfer skill."""

from decimal import Decimal

from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.base import ERC20BaseTool
from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.erc20.utils import get_token_details


class TransferInput(BaseModel):
    """Input schema for ERC20 transfer."""

    contract_address: str = Field(
        ..., description="The contract address of the ERC20 token to transfer"
    )
    destination_address: str = Field(
        ..., description="The address to send the tokens to"
    )
    amount: str = Field(
        ...,
        description="The amount to transfer in whole units (e.g. '10.5' for 10.5 USDC)",
    )


class ERC20Transfer(ERC20BaseTool):
    """Transfer ERC20 tokens to another address.

    This tool transfers ERC20 tokens from the wallet to a destination address.
    """

    name: str = "erc20_transfer"
    description: str = """Transfer ERC20 tokens from the wallet to another onchain address.

Inputs:
- contract_address: The contract address of the token to transfer
- destination_address: The address to send the tokens to
- amount: The amount to transfer in whole units (e.g. '10.5' for 10.5 USDC)

Important notes:
- Never assume token or destination addresses, they have to be provided as inputs
- If only token symbol is provided, use the erc20_get_token_address tool to get the token address first
- Ensure sufficient balance of the input asset before transferring
- When sending native assets (e.g. 'eth' on base-mainnet), ensure there is sufficient balance for the transfer itself AND the gas cost
"""
    args_schema: type[BaseModel] = TransferInput

    async def _arun(
        self,
        contract_address: str,
        destination_address: str,
        amount: str,
    ) -> str:
        """Transfer ERC20 tokens to a destination address.

        Args:
            contract_address: The contract address of the ERC20 token.
            destination_address: The address to send the tokens to.
            amount: The amount to transfer in whole units.

        Returns:
            A message containing the transfer result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            w3 = Web3()
            checksum_contract = w3.to_checksum_address(contract_address)
            checksum_destination = w3.to_checksum_address(destination_address)

            # Get token details
            token_details = await get_token_details(wallet, contract_address)

            if not token_details:
                return (
                    f"Error: Could not fetch token details for {contract_address}. "
                    "Please verify the token address is correct."
                )

            # Convert amount from whole units to atomic units
            amount_in_atomic_units = int(Decimal(amount) * (10**token_details.decimals))

            # Check token balance
            if token_details.balance < amount_in_atomic_units:
                return (
                    f"Error: Insufficient {token_details.name} ({contract_address}) token balance. "
                    f"Requested to send {amount} of {token_details.name}, "
                    f"but only {token_details.formatted_balance} is available."
                )

            # Guardrails to prevent loss of funds
            if contract_address.lower() == destination_address.lower():
                return (
                    "Error: Transfer destination is the token contract address. "
                    "Refusing transfer to prevent loss of funds."
                )

            # Check if destination is also an ERC20 token contract
            # This helps prevent accidental transfers to token contracts
            destination_token_details = await get_token_details(
                wallet, destination_address
            )
            if destination_token_details:
                return (
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
            await wallet.wait_for_transaction_receipt(tx_hash)

            return (
                f"Transferred {amount} of {token_details.name} ({contract_address}) "
                f"to {destination_address}.\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error transferring the asset: {e!s}"
