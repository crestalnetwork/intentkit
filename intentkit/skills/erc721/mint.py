"""ERC721 mint skill."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc721.base import ERC721BaseTool
from intentkit.skills.erc721.constants import ERC721_ABI


class MintInput(BaseModel):
    """Input schema for ERC721 mint."""

    contract_address: str = Field(
        ..., description="The contract address of the ERC721 NFT to mint"
    )
    destination: str = Field(
        ..., description="The onchain address that will receive the minted NFT"
    )


class ERC721Mint(ERC721BaseTool):
    """Mint an NFT (ERC721) to a specified destination address.

    This tool mints a new NFT from a contract to a destination address.
    Note: The contract must support the mint function and the wallet
    must have permission to mint.
    """

    name: str = "erc721_mint"
    description: str = """Mint an NFT (ERC-721) to a specified destination address onchain via a contract invocation.

Inputs:
- contract_address: The contract address of the NFT to mint
- destination: The onchain address that will receive the minted NFT

Important notes:
- Do not use the contract address as the destination address
- If you are unsure of the destination address, please ask the user before proceeding
- The contract must support the mint function
- The wallet must have permission to mint (some contracts restrict who can mint)
"""
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
                return (
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
            return f"Error minting NFT {contract_address} to {destination}: {e!s}"
