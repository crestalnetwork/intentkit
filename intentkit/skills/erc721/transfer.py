"""ERC721 transfer skill."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc721.base import ERC721BaseTool
from intentkit.skills.erc721.constants import ERC721_ABI


class TransferInput(BaseModel):
    """Input schema for ERC721 transfer."""

    contract_address: str = Field(..., description="The NFT contract address")
    token_id: str = Field(..., description="The ID of the specific NFT to transfer")
    destination: str = Field(..., description="The onchain address to send the NFT to")
    from_address: str | None = Field(
        default=None,
        description="The address to transfer from. If not provided, uses the wallet's address",
    )


class ERC721Transfer(ERC721BaseTool):
    """Transfer an NFT (ERC721 token) to another address.

    This tool transfers an NFT from the wallet to a destination address
    using the transferFrom function.
    """

    name: str = "erc721_transfer"
    description: str = """Transfer an NFT (ERC721 token) from the wallet to another onchain address.

Inputs:
- contract_address: The NFT contract address
- token_id: The ID of the specific NFT to transfer
- destination: Onchain address to send the NFT to
- from_address: (Optional) The address to transfer from. If not provided, uses the wallet's address

Important notes:
- Ensure you have ownership of the NFT before attempting transfer
- Ensure there is sufficient native token balance for gas fees
- The wallet must either own the NFT or have approval to transfer it
"""
    args_schema: ArgsSchema | None = TransferInput

    async def _arun(
        self,
        contract_address: str,
        token_id: str,
        destination: str,
        from_address: str | None = None,
    ) -> str:
        """Transfer an NFT to a destination address.

        Args:
            contract_address: The NFT contract address.
            token_id: The ID of the NFT to transfer.
            destination: The address to send the NFT to.
            from_address: The address to transfer from. Uses wallet address if not provided.

        Returns:
            A message containing the transfer result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            w3 = Web3()
            checksum_contract = w3.to_checksum_address(contract_address)
            checksum_destination = w3.to_checksum_address(destination)
            checksum_from = w3.to_checksum_address(
                from_address if from_address else wallet.address
            )

            # Encode transferFrom function
            contract = w3.eth.contract(address=checksum_contract, abi=ERC721_ABI)
            data = contract.encode_abi(
                "transferFrom",
                [checksum_from, checksum_destination, int(token_id)],
            )

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=checksum_contract,
                data=data,
            )

            # Wait for receipt
            await wallet.wait_for_transaction_receipt(tx_hash)

            return (
                f"Successfully transferred NFT {contract_address} with tokenId "
                f"{token_id} to {destination}\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return (
                f"Error transferring NFT {contract_address} with tokenId "
                f"{token_id} to {destination}: {e!s}"
            )
