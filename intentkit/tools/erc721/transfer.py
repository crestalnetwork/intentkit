"""ERC721 transfer tool."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.erc721.base import ERC721BaseTool
from intentkit.tools.erc721.constants import ERC721_ABI
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION


class TransferInput(BaseModel):
    """Input schema for ERC721 transfer."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)
    contract_address: str = Field(..., description="NFT contract address")
    token_id: str = Field(..., description="Token ID of the NFT")
    destination: str = Field(..., description="Recipient address")
    from_address: str | None = Field(
        default=None,
        description="Sender address. Defaults to the wallet_address argument.",
    )


class ERC721Transfer(ERC721BaseTool):
    """Transfer an NFT (ERC721 token) to another address.

    This tool transfers an NFT from the wallet to a destination address
    using the transferFrom function.
    """

    name: str = "erc721_transfer"
    title: str = "Transfer NFT"
    team_only: bool = True
    description: str = "Transfer an ERC721 NFT to another address. Wallet must own or have approval for the NFT. Ensure sufficient gas."
    args_schema: ArgsSchema | None = TransferInput

    async def _arun(
        self,
        wallet_address: str,
        contract_address: str,
        token_id: str,
        destination: str,
        from_address: str | None = None,
    ) -> str:
        """Transfer an NFT to a destination address.

        Args:
            wallet_address: The team wallet address to send from.
            contract_address: The NFT contract address.
            token_id: The ID of the NFT to transfer.
            destination: The address to send the NFT to.
            from_address: The address to transfer from. Uses wallet_address if not provided.

        Returns:
            A message containing the transfer result or error details.
        """
        try:
            # Get the unified wallet (signing-capable, guarded)
            wallet = await self.get_unified_wallet(wallet_address)

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
            await wallet.wait_for_receipt(tx_hash)

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
