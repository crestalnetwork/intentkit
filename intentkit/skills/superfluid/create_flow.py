"""Superfluid create_flow skill - Create a money stream."""

from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.superfluid.base import SuperfluidBaseTool
from intentkit.skills.superfluid.constants import (
    CREATE_FLOW_ABI,
    SUPERFLUID_HOST_ADDRESS,
)


class CreateFlowInput(BaseModel):
    """Input schema for create_flow."""

    token_address: str = Field(
        ..., description="The Super token contract address to stream"
    )
    recipient: str = Field(
        ..., description="The wallet address to receive the token stream"
    )
    flow_rate: str = Field(
        ...,
        description="The flowrate of the stream in wei per second (must be a whole number, no decimals)",
    )


class SuperfluidCreateFlow(SuperfluidBaseTool):
    """Create a money stream using Superfluid.

    This tool creates a continuous token stream to a recipient address
    using the Superfluid protocol. The stream will continuously transfer
    tokens at the specified rate until stopped.
    """

    name: str = "superfluid_create_flow"
    description: str = """Create a money stream to a specified recipient using Superfluid.

Inputs:
- token_address: The Super token contract address to stream
- recipient: The wallet address to receive the token stream
- flow_rate: The flowrate of the stream in wei per second

Important notes:
- The token must be a Superfluid Super token. If errors occur, confirm that the token is a valid Superfluid Super token.
- The flowrate cannot have any decimal points, since the unit of measurement is wei per second.
- Make sure to use the exact amount provided.
- 1 wei = 0.000000000000000001 ETH
- Example: To stream 1 token per month, calculate: 1e18 / (30 * 24 * 60 * 60) ≈ 385802469135802 wei/second
"""
    args_schema: type[BaseModel] = CreateFlowInput

    async def _arun(
        self,
        token_address: str,
        recipient: str,
        flow_rate: str,
    ) -> str:
        """Create a money stream using Superfluid.

        Args:
            token_address: The Super token contract address.
            recipient: The address to receive the stream.
            flow_rate: The flowrate in wei per second.

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

            # Encode createFlow function
            contract = w3.eth.contract(address=checksum_host, abi=CREATE_FLOW_ABI)
            data = contract.encode_abi(
                "createFlow",
                [
                    checksum_token,
                    wallet.address,  # sender
                    checksum_recipient,
                    int(flow_rate),
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
                f"Flow created successfully.\n"
                f"Token: {token_address}\n"
                f"Recipient: {recipient}\n"
                f"Flow rate: {flow_rate} wei/second\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error creating flow: {e!s}"
