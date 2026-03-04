"""Superfluid delete_flow skill - Delete an existing money stream."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.superfluid.base import SuperfluidBaseTool
from intentkit.skills.superfluid.constants import (
    DELETE_FLOW_ABI,
    SUPERFLUID_HOST_ADDRESS,
)


class DeleteFlowInput(BaseModel):
    """Input schema for delete_flow."""

    token_address: str = Field(..., description="Super Token contract address")
    recipient: str = Field(
        ...,
        description="Address receiving or sending the stream",
    )


class SuperfluidDeleteFlow(SuperfluidBaseTool):
    """Delete an existing money stream using Superfluid.

    This tool stops and deletes an existing token stream
    to a recipient address using the Superfluid protocol.
    """

    name: str = "superfluid_delete_flow"
    description: str = (
        "Delete an existing Superfluid money stream. The stream stops immediately."
    )
    args_schema: ArgsSchema | None = DeleteFlowInput

    async def _arun(
        self,
        token_address: str,
        recipient: str,
    ) -> str:
        """Delete an existing money stream using Superfluid.

        Args:
            token_address: The Super token contract address.
            recipient: The address receiving or sending the stream.

        Returns:
            A message containing the result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            w3 = Web3()
            checksum_token = w3.to_checksum_address(token_address)
            checksum_recipient = w3.to_checksum_address(recipient)
            checksum_host = w3.to_checksum_address(SUPERFLUID_HOST_ADDRESS)

            # Encode deleteFlow function
            contract = w3.eth.contract(address=checksum_host, abi=DELETE_FLOW_ABI)
            data = contract.encode_abi(
                "deleteFlow",
                [
                    checksum_token,
                    wallet.address,  # sender
                    checksum_recipient,
                    b"",  # userData
                ],
            )

            # Send transaction
            tx_hash = await wallet.send_transaction(
                to=checksum_host,
                data=data,
            )

            # Wait for receipt
            await wallet.wait_for_transaction_receipt(tx_hash)

            return (
                f"Flow deleted successfully.\n"
                f"Token: {token_address}\n"
                f"Recipient: {recipient}\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            raise ToolException(f"Error deleting flow: {e!s}")
