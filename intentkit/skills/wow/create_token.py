"""WOW create token skill."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.wow.base import WowBaseTool
from intentkit.skills.wow.constants import (
    GENERIC_TOKEN_METADATA_URI,
    WOW_FACTORY_ABI,
)
from intentkit.skills.wow.utils import get_factory_address


class CreateTokenInput(BaseModel):
    """Input schema for creating WOW tokens."""

    name: str = Field(..., description="The name of the token to create, e.g. WowCoin")
    symbol: str = Field(..., description="The symbol of the token to create, e.g. WOW")
    token_uri: str | None = Field(
        None, description="The URI of the token metadata to store on IPFS (optional)"
    )


class WowCreateToken(WowBaseTool):
    """Create a new WOW token using the factory contract.

    This tool creates a new Zora WOW ERC20 memecoin using a bonding curve.
    """

    name: str = "wow_create_token"
    description: str = """Create a Zora WOW ERC20 memecoin (bonding curve token) using the WOW factory.

This tool can only be used to create a Zora WOW ERC20 memecoin. Do not use this tool
for any other purpose, or for creating other types of tokens.

Inputs:
- name: The name of the token to create (e.g. WowCoin)
- symbol: The symbol of the token to create (e.g. WOW)
- token_uri: (Optional) The URI of the token metadata to store on IPFS

Important notes:
- Uses a bonding curve - no upfront liquidity needed
- The token will start trading immediately after creation
- Anyone can buy/sell the token once created
"""
    args_schema: ArgsSchema | None = CreateTokenInput

    async def _arun(
        self,
        name: str,
        symbol: str,
        token_uri: str | None = None,
    ) -> str:
        """Create a new WOW token.

        Args:
            name: The name of the token to create.
            symbol: The symbol of the token to create.
            token_uri: Optional URI for token metadata.

        Returns:
            A message containing the creation details or error message.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()

            # Get factory address for this chain
            factory_address = get_factory_address(wallet.chain_id)

            if not Web3.is_address(factory_address):
                return f"Error: Invalid factory address: {factory_address}"

            # Use generic metadata URI if none provided
            final_token_uri = token_uri or GENERIC_TOKEN_METADATA_URI

            # Get creator address
            creator_address = wallet.address

            # Build deploy arguments
            deploy_args = [
                Web3.to_checksum_address(creator_address),  # _tokenCreator
                Web3.to_checksum_address(
                    "0x0000000000000000000000000000000000000000"
                ),  # _platformReferrer
                final_token_uri,  # _tokenURI
                name,  # _name
                symbol,  # _symbol
            ]

            # Encode deploy function
            w3 = Web3()
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(factory_address),
                abi=WOW_FACTORY_ABI,
            )

            encoded_data = contract.encode_abi("deploy", deploy_args)

            # Send transaction (no ETH value needed)
            tx_hash = await wallet.send_transaction(
                to=factory_address,
                data=encoded_data,
            )

            # Wait for receipt
            receipt = await wallet.wait_for_transaction_receipt(tx_hash)

            if receipt.get("status") == 0:
                return (
                    f"Transaction failed with hash: {tx_hash}. "
                    "The transaction failed to execute."
                )

            # Get network ID for display
            network_id = self.get_agent_network_id() or "unknown"

            return (
                f"Successfully created WOW ERC20 memecoin!\n"
                f"Name: {name}\n"
                f"Symbol: {symbol}\n"
                f"Network: {network_id}\n"
                f"Transaction hash: {tx_hash}\n\n"
                "Note: The token contract address can be found in the transaction logs."
            )

        except Exception as e:
            return f"Error creating Zora WOW ERC20 memecoin: {e!s}"
