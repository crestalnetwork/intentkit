"""ERC721 get_balance skill."""

from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc721.base import ERC721BaseTool
from intentkit.skills.erc721.constants import ERC721_ABI


class GetBalanceInput(BaseModel):
    """Input schema for ERC721 get_balance."""

    contract_address: str = Field(
        ..., description="The contract address of the ERC721 NFT collection"
    )
    address: str | None = Field(
        default=None,
        description="The address to check the NFT balance for. If not provided, uses the wallet's address",
    )


class ERC721GetBalance(ERC721BaseTool):
    """Get the NFT balance for an address from an ERC721 contract.

    This tool queries an ERC721 NFT contract to get the token balance
    (number of NFTs owned) for a specific address.
    """

    name: str = "erc721_get_balance"
    description: str = """Get the NFT (ERC721 token) balance for a given address.

Inputs:
- contract_address: The NFT contract address to check balance for
- address: (Optional) The address to check NFT balance for. If not provided, uses the wallet's address

Returns the number of NFTs owned by the address for the specified collection.
"""
    args_schema: type[BaseModel] = GetBalanceInput

    async def _arun(
        self,
        contract_address: str,
        address: str | None = None,
    ) -> str:
        """Get the NFT balance for a given address and contract.

        Args:
            contract_address: The address of the ERC721 NFT contract.
            address: The address to check NFT balance for. Uses wallet address if not provided.

        Returns:
            A message containing the NFT balance or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            # Use wallet address if not provided
            check_address = address if address else wallet.address
            checksum_address = Web3.to_checksum_address(check_address)
            checksum_contract = Web3.to_checksum_address(contract_address)

            # Read balance from contract
            balance = await wallet.read_contract(
                contract_address=checksum_contract,
                abi=ERC721_ABI,
                function_name="balanceOf",
                args=[checksum_address],
            )

            return (
                f"Balance of NFTs for contract {contract_address} "
                f"at address {checksum_address} is {balance}"
            )

        except Exception as e:
            return f"Error getting NFT balance for contract {contract_address}: {e!s}"
