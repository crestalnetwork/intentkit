"""Morpho deposit skill - Deposit assets into a Morpho Vault."""

from decimal import Decimal

from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import METAMORPHO_ABI, SUPPORTED_NETWORKS


class DepositInput(BaseModel):
    """Input schema for Morpho deposit."""

    vault_address: str = Field(
        ..., description="The address of the Morpho Vault to deposit to"
    )
    token_address: str = Field(..., description="The address of the token to deposit")
    assets: str = Field(
        ...,
        description="The amount of assets to deposit in whole units (e.g., '1' for 1 WETH, '0.1' for 0.1 WETH)",
    )
    receiver: str = Field(..., description="The address to receive the vault shares")


class MorphoDeposit(MorphoBaseTool):
    """Deposit assets into a Morpho Vault.

    This tool deposits assets into a Morpho Vault and receives shares
    representing the deposited amount.
    """

    name: str = "morpho_deposit"
    description: str = """Deposit assets into a Morpho Vault.

Inputs:
- vault_address: The address of the Morpho Vault to deposit to
- token_address: The address of the token to deposit (must match the vault's underlying token)
- assets: The amount of assets to deposit in whole units (e.g., '1' for 1 WETH)
- receiver: The address to receive the vault shares

Important notes:
- Make sure to use the exact amount provided. Do not convert units for assets for this action.
- Please use a token address (example 0x4200000000000000000000000000000000000006) for the token_address field.
- The token must be approved for the vault to spend before depositing.
- If you are unsure of the token address, please clarify what the requested token address is before continuing.
"""
    args_schema: type[BaseModel] = DepositInput

    async def _arun(
        self,
        vault_address: str,
        token_address: str,
        assets: str,
        receiver: str,
    ) -> str:
        """Deposit assets into a Morpho Vault.

        Args:
            vault_address: The address of the Morpho Vault.
            token_address: The address of the token to deposit.
            assets: The amount of assets to deposit in whole units.
            receiver: The address to receive the shares.

        Returns:
            A message containing the result or error details.
        """
        try:
            # Get the unified wallet
            wallet = await self.get_unified_wallet()
            network_id = wallet.network_id

            # Check if network is supported
            if network_id not in SUPPORTED_NETWORKS:
                return (
                    f"Error: Morpho is not supported on network {network_id}. "
                    f"Supported networks: {', '.join(SUPPORTED_NETWORKS)}"
                )

            # Validate assets amount
            assets_decimal = Decimal(assets)
            if assets_decimal <= Decimal("0"):
                return "Error: Assets amount must be greater than 0"

            w3 = Web3()
            checksum_vault = w3.to_checksum_address(vault_address)
            checksum_token = w3.to_checksum_address(token_address)
            checksum_receiver = w3.to_checksum_address(receiver)

            # Get token decimals
            decimals = await wallet.read_contract(
                contract_address=checksum_token,
                abi=ERC20_ABI,
                function_name="decimals",
                args=[],
            )

            # Convert assets to atomic units
            atomic_assets = int(assets_decimal * (10**decimals))

            # Approve the vault to spend tokens
            approve_contract = w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
            approve_data = approve_contract.encode_abi(
                "approve", [checksum_vault, atomic_assets]
            )

            # Send approval transaction
            approve_tx_hash = await wallet.send_transaction(
                to=checksum_token,
                data=approve_data,
            )

            # Wait for approval
            receipt = await wallet.wait_for_transaction_receipt(approve_tx_hash)
            if receipt.get("status", 1) == 0:
                return f"Error: Approval transaction failed. Hash: {approve_tx_hash}"

            # Encode deposit function
            morpho_contract = w3.eth.contract(
                address=checksum_vault, abi=METAMORPHO_ABI
            )
            deposit_data = morpho_contract.encode_abi(
                "deposit", [atomic_assets, checksum_receiver]
            )

            # Send deposit transaction
            tx_hash = await wallet.send_transaction(
                to=checksum_vault,
                data=deposit_data,
            )

            # Wait for receipt
            await wallet.wait_for_transaction_receipt(tx_hash)

            return (
                f"Deposited {assets} to Morpho Vault {vault_address}\n"
                f"Receiver: {receiver}\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error depositing to Morpho Vault: {e!s}"
