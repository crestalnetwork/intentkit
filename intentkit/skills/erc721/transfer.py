"""ERC721 transfer skill."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc721.base import ERC721BaseTool
from intentkit.skills.erc721.constants import ERC721_ABI


class TransferInput(BaseModel):
    """Input schema for ERC721 transfer."""

    contract_address: str = Field(..., description="NFT contract address")
    token_id: str = Field(..., description="Token ID of the NFT")
    destination: str = Field(..., description="Recipient address")
    from_address: str | None = Field(
        default=None,
        description="Sender address. Defaults to wallet address.",
    )


class ERC721Transfer(ERC721BaseTool):
    """Transfer an NFT (ERC721 token) to another address.

    This tool transfers an NFT from the wallet to a destination address
    using the transferFrom function.
    """

    name: str = "erc721_transfer"
    description: str = "Transfer an ERC721 NFT to another address. Wallet must own or have approval for the NFT. Ensure sufficient gas."
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
            await wallet.wait_for_transaction_receipt(tx_hash)  # pyright: ignore[reportAttributeAccessIssue]

            return (
                f"Successfully transferred NFT {contract_address} with tokenId "
                f"{token_id} to {destination}\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            raise ToolException(
                f"Error transferring NFT {contract_address} with tokenId "
                f"{token_id} to {destination}: {e!s}"
            )
