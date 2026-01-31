"""Basename registration skill."""

from decimal import Decimal

from ens import ENS
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.basename.base import BasenameBaseTool
from intentkit.skills.basename.constants import (
    BASENAMES_REGISTRAR_CONTROLLER_ADDRESS_MAINNET,
    BASENAMES_REGISTRAR_CONTROLLER_ADDRESS_TESTNET,
    L2_RESOLVER_ABI,
    L2_RESOLVER_ADDRESS_MAINNET,
    L2_RESOLVER_ADDRESS_TESTNET,
    REGISTRAR_ABI,
    REGISTRATION_DURATION,
    SUPPORTED_NETWORKS,
)


class RegisterBasenameInput(BaseModel):
    """Input schema for registering a Basename."""

    basename: str = Field(
        ...,
        description=(
            "The Basename to register (e.g., 'myname.base.eth' for mainnet "
            "or 'myname.basetest.eth' for testnet)"
        ),
    )
    amount: str = Field(
        default="0.002",
        description="The amount of ETH to pay for registration. Default is 0.002 ETH.",
    )


class BasenameRegister(BasenameBaseTool):
    """Register a Basename ENS-style domain.

    This tool registers a Basename for the agent's wallet address on Base network.
    """

    name: str = "basename_register_basename"
    description: str = """Register a Basename ENS-style domain for the agent.

This tool will register a Basename for the agent. The agent should have a wallet
associated to register a Basename.

When your network ID is 'base-mainnet' (also sometimes known simply as 'base'),
the name must end with .base.eth, and when your network ID is 'base-sepolia',
it must end with .basetest.eth.

Do not suggest any alternatives and never try to register a Basename with another
postfix. The prefix of the name must be unique so if the registration of the
Basename fails, you should prompt to try again with a more unique name.

Inputs:
- basename: The Basename to register (e.g., 'example.base.eth' or 'example.basetest.eth')
- amount: The amount of ETH to pay for registration. Default is 0.002 ETH.

Important notes:
- Ensure you have sufficient ETH balance for registration fee plus gas
- Names are first-come, first-served - if registration fails, try a more unique name
"""
    args_schema: type[BaseModel] = RegisterBasenameInput

    async def _arun(
        self,
        basename: str,
        amount: str = "0.002",
    ) -> str:
        """Register a Basename for the agent.

        Args:
            basename: The Basename to register.
            amount: The amount of ETH to pay for registration.

        Returns:
            A message containing the registration result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()
            network_id = self.get_agent_network_id()

            # Validate network
            if network_id not in SUPPORTED_NETWORKS:
                return (
                    f"Error: Basename registration is only supported on Base networks. "
                    f"Current network: {network_id}. "
                    f"Supported networks: {', '.join(SUPPORTED_NETWORKS)}"
                )

            is_mainnet = network_id == "base-mainnet"

            # Ensure the basename has the correct suffix
            suffix = ".base.eth" if is_mainnet else ".basetest.eth"
            if not basename.endswith(suffix):
                basename = basename + suffix

            # Get addresses
            address = Web3.to_checksum_address(wallet.address)
            l2_resolver_address = Web3.to_checksum_address(
                L2_RESOLVER_ADDRESS_MAINNET
                if is_mainnet
                else L2_RESOLVER_ADDRESS_TESTNET
            )
            contract_address = Web3.to_checksum_address(
                BASENAMES_REGISTRAR_CONTROLLER_ADDRESS_MAINNET
                if is_mainnet
                else BASENAMES_REGISTRAR_CONTROLLER_ADDRESS_TESTNET
            )

            # Create contract instances for encoding
            w3 = Web3()
            resolver_contract = w3.eth.contract(abi=L2_RESOLVER_ABI)
            registrar_contract = w3.eth.contract(abi=REGISTRAR_ABI)

            # Compute namehash using ENS class method
            name_hash = ENS.namehash(basename)

            # Encode resolver data
            address_data = resolver_contract.encode_abi(
                "setAddr", args=[name_hash, address]
            )
            name_data = resolver_contract.encode_abi(
                "setName", args=[name_hash, basename]
            )

            # Build register request
            register_request = {
                "name": basename.replace(suffix, ""),
                "owner": address,
                "duration": int(REGISTRATION_DURATION),
                "resolver": l2_resolver_address,
                "data": [address_data, name_data],
                "reverseRecord": True,
            }

            # Encode the register call
            data = registrar_contract.encode_abi("register", args=[register_request])

            # Convert amount to wei
            value_wei = int(Decimal(amount) * Decimal(10**18))

            # Send the transaction
            tx_hash = await wallet.send_transaction(
                to=contract_address,
                value=value_wei,
                data=data,
            )

            # Wait for receipt
            receipt = await wallet.wait_for_transaction_receipt(tx_hash)

            if receipt.get("status") == 0:
                return (
                    f"Transaction failed with hash: {tx_hash}. "
                    "The basename may already be taken. Try a more unique name."
                )

            return (
                f"Successfully registered basename {basename} for address {address}.\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            error_msg = str(e)
            if "insufficient funds" in error_msg.lower():
                return (
                    f"Error registering basename: Insufficient ETH balance. "
                    f"Registration requires {amount} ETH plus gas fees."
                )
            return f"Error registering basename: {error_msg}"
