"""Superfluid update_flow skill - Update an existing money stream."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.superfluid.base import SuperfluidBaseTool
from intentkit.skills.superfluid.constants import (
    SUPERFLUID_HOST_ADDRESS,
    UPDATE_FLOW_ABI,
)


class UpdateFlowInput(BaseModel):
    """Input schema for update_flow."""

    token_address: str = Field(
        ..., description="The Super token contract address being streamed"
    )
    recipient: str = Field(
        ..., description="The wallet address that is receiving the token stream"
    )
    new_flow_rate: str = Field(
        ...,
        description="The new flowrate of the stream in wei per second (must be a whole number, no decimals)",
    )


class SuperfluidUpdateFlow(SuperfluidBaseTool):
    """Update an existing money stream using Superfluid.

    This tool updates the flow rate of an existing token stream
    to a recipient address using the Superfluid protocol.
    """

    name: str = "superfluid_update_flow"
    description: str = """Update an existing money stream to a specified recipient using Superfluid.

Inputs:
- token_address: The Super token contract address being streamed
- recipient: The wallet address that is receiving the token stream
- new_flow_rate: The new flowrate of the stream in wei per second

Important notes:
- The flowrate cannot have any decimal points, since the unit of measurement is wei per second.
- Make sure to use the exact amount provided.
- 1 wei = 0.000000000000000001 ETH
- A stream must already exist to the recipient before it can be updated.
"""
    args_schema: ArgsSchema | None = UpdateFlowInput

    async def _arun(
        self,
        token_address: str,
        recipient: str,
        new_flow_rate: str,
    ) -> str:
        """Update an existing money stream using Superfluid.

        Args:
            token_address: The Super token contract address.
            recipient: The address receiving the stream.
            new_flow_rate: The new flowrate in wei per second.

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

            # Encode updateFlow function
            contract = w3.eth.contract(address=checksum_host, abi=UPDATE_FLOW_ABI)
            data = contract.encode_abi(
                "updateFlow",
                [
                    checksum_token,
                    wallet.address,  # sender
                    checksum_recipient,
                    int(new_flow_rate),
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
                f"Flow updated successfully.\n"
                f"Token: {token_address}\n"
                f"Recipient: {recipient}\n"
                f"New flow rate: {new_flow_rate} wei/second\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error updating flow: {e!s}"
