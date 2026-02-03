"""ERC20 get_balance skill."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.base import ERC20BaseTool
from intentkit.skills.erc20.utils import get_token_details


class GetBalanceInput(BaseModel):
    """Input schema for ERC20 get_balance."""

    contract_address: str = Field(
        ..., description="The contract address of the ERC20 token"
    )
    address: str | None = Field(
        default=None,
        description="The address to check the balance for. If not provided, uses the wallet's address",
    )


class ERC20GetBalance(ERC20BaseTool):
    """Get the balance of an ERC20 token for a given address.

    This tool queries an ERC20 token contract to get the token balance
    for a specific address.
    """

    name: str = "erc20_get_balance"
    description: str = """Get the balance of an ERC20 token for a given address.

Inputs:
- contract_address: The contract address of the token to get the balance for
- address: (Optional) The address to check the balance for. If not provided, uses the wallet's address

Important notes:
- Never assume token or address, they have to be provided as inputs
- If only token symbol is provided, use the erc20_get_token_address tool to get the token address first
"""
    args_schema: ArgsSchema | None = GetBalanceInput

    async def _arun(
        self,
        contract_address: str,
        address: str | None = None,
    ) -> str:
        """Get the balance of an ERC20 token for a given address.

        Args:
            contract_address: The contract address of the ERC20 token.
            address: The address to check the balance for. Uses wallet address if not provided.

        Returns:
            A message containing the balance or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            # Use wallet address if not provided
            check_address = address if address else wallet.address
            checksum_address = Web3.to_checksum_address(check_address)

            # Get token details (includes balance)
            token_details = await get_token_details(
                wallet, contract_address, checksum_address
            )

            if not token_details:
                return f"Error: Could not fetch token details for {contract_address}. Please verify the token address is correct."

            return (
                f"Balance of {token_details.name} ({token_details.symbol}) at address "
                f"{checksum_address} is {token_details.formatted_balance} "
                f"(contract: {contract_address})"
            )

        except Exception as e:
            return f"Error getting balance: {e!s}"
