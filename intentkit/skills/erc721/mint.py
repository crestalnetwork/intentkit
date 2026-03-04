"""ERC721 mint skill."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc721.base import ERC721BaseTool
from intentkit.skills.erc721.constants import ERC721_ABI


class MintInput(BaseModel):
    """Input schema for ERC721 mint."""

    contract_address: str = Field(..., description="ERC721 NFT contract address")
    destination: str = Field(..., description="Address to receive the minted NFT")


class ERC721Mint(ERC721BaseTool):
    """Mint an NFT (ERC721) to a specified destination address.

    This tool mints a new NFT from a contract to a destination address.
    Note: The contract must support the mint function and the wallet
    must have permission to mint.
    """

    name: str = "erc721_mint"
    description: str = "Mint an ERC721 NFT to a destination address. Do not use the contract address as destination. The contract must support mint and wallet must have permission."
    args_schema: ArgsSchema | None = MintInput

    async def _arun(
        self,
        contract_address: str,
        destination: str,
    ) -> str:
        """Mint an NFT to a destination address.

        Args:
            contract_address: The NFT contract address.
            destination: The address to receive the minted NFT.

        Returns:
            A message containing the mint result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            w3 = Web3()
            checksum_contract = w3.to_checksum_address(contract_address)
            checksum_destination = w3.to_checksum_address(destination)

            # Validate that destination is not the contract itself
            if checksum_contract.lower() == checksum_destination.lower():
                raise ToolException(
                    "Error: Destination address is the same as the contract address. "
                    "Please provide a valid recipient address."
                )

            # Encode mint function (mint(address to, uint256 tokenId))
            # Note: Many NFT contracts use different mint signatures
            # This uses a common pattern: mint(address, uint256)
            contract = w3.eth.contract(address=checksum_contract, abi=ERC721_ABI)
            data = contract.encode_abi("mint", [checksum_destination, 1])

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=checksum_contract,
                data=data,
            )

            # Wait for receipt
            receipt = await wallet.wait_for_transaction_receipt(tx_hash)

            # Check transaction status
            status = receipt.get("status", 1)
            if status == 0:
                return (
                    f"Transaction failed with hash: {tx_hash}. "
                    "The transaction was reverted. The contract may not support "
                    "this mint function or the wallet may not have permission to mint."
                )

            return (
                f"Successfully minted NFT from contract {contract_address} "
                f"to {destination}\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            raise ToolException(
                f"Error minting NFT {contract_address} to {destination}: {e!s}"
            )
