"""ERC721 get_balance tool."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.erc721.base import ERC721BaseTool
from intentkit.tools.erc721.constants import ERC721_ABI
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION


class GetBalanceInput(BaseModel):
    """Input schema for ERC721 get_balance."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)
    contract_address: str = Field(..., description="ERC721 NFT contract address")
    address: str | None = Field(
        default=None,
        description="Address to check. Defaults to the wallet_address argument.",
    )


class ERC721GetBalance(ERC721BaseTool):
    """Get the NFT balance for an address from an ERC721 contract.

    This tool queries an ERC721 NFT contract to get the token balance
    (number of NFTs owned) for a specific address.
    """

    name: str = "erc721_get_balance"
    title: str = "Get NFT Balance"
    description: str = (
        "Get the number of NFTs (ERC721) owned by an address for a given contract."
    )
    args_schema: ArgsSchema | None = GetBalanceInput

    async def _arun(
        self,
        wallet_address: str,
        contract_address: str,
        address: str | None = None,
    ) -> str:
        """Get the NFT balance for a given address and contract.

        Args:
            wallet_address: The team wallet address to use.
            contract_address: The address of the ERC721 NFT contract.
            address: The address to check NFT balance for. Uses wallet_address if not provided.

        Returns:
            A message containing the NFT balance or error details.
        """
        try:
            checksum_address = Web3.to_checksum_address(address or wallet_address)
            checksum_contract = Web3.to_checksum_address(contract_address)

            # Read balance on the wallet's network (also validates that the
            # wallet belongs to the team).
            w3 = await self.web3_client(wallet_address)
            contract = w3.eth.contract(address=checksum_contract, abi=ERC721_ABI)
            balance = await contract.functions.balanceOf(checksum_address).call()

            return (
                f"Balance of NFTs for contract {contract_address} "
                f"at address {checksum_address} is {balance}"
            )

        except Exception as e:
            raise ToolException(
                f"Error getting NFT balance for contract {contract_address}: {e!s}"
            )
