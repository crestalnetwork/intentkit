"""ERC20 get_balance tool."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.erc20.base import ERC20BaseTool
from intentkit.tools.erc20.utils import get_token_details
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION


class GetBalanceInput(BaseModel):
    """Input schema for ERC20 get_balance."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)
    contract_address: str = Field(..., description="ERC20 token contract address")
    address: str | None = Field(
        default=None,
        description="Address to check balance for. Defaults to the wallet_address argument.",
    )


class ERC20GetBalance(ERC20BaseTool):
    """Get the balance of an ERC20 token for a given address.

    This tool queries an ERC20 token contract to get the token balance
    for a specific address.
    """

    name: str = "erc20_get_balance"
    title: str = "Get ERC20 Balance"
    description: str = "Get an ERC20 token balance. Use erc20_get_token_address first if only a symbol is provided."
    args_schema: ArgsSchema | None = GetBalanceInput

    @override
    async def _arun(
        self,
        wallet_address: str,
        contract_address: str,
        address: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Get the balance of an ERC20 token for a given address.

        Args:
            wallet_address: The team wallet address to use.
            contract_address: The contract address of the ERC20 token.
            address: The address to check the balance for. Uses wallet_address if not provided.

        Returns:
            A message containing the balance or error details.
        """
        try:
            # Read-only: validate the wallet belongs to the team, no signing.
            await self.resolve_wallet(wallet_address)

            # Use the selected wallet address if no explicit address is given
            checksum_address = Web3.to_checksum_address(address or wallet_address)

            # Get token details (includes balance)
            token_details = await get_token_details(
                self.web3_client(), contract_address, checksum_address
            )

            if not token_details:
                raise ToolException(
                    f"Error: Could not fetch token details for {contract_address}. Please verify the token address is correct."
                )
            return (
                f"Balance of {token_details.name} ({token_details.symbol}) at address "
                f"{checksum_address} is {token_details.formatted_balance} "
                f"(contract: {contract_address})"
            )

        except Exception as e:
            raise ToolException(f"Error getting balance: {e!s}")
