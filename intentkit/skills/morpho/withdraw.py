"""Morpho withdraw skill - Withdraw assets from a Morpho Vault."""

from decimal import Decimal

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import METAMORPHO_ABI, SUPPORTED_NETWORKS


class WithdrawInput(BaseModel):
    """Input schema for Morpho withdraw."""

    vault_address: str = Field(
        ..., description="The address of the Morpho Vault to withdraw from"
    )
    assets: str = Field(
        ...,
        description="The amount of assets to withdraw in whole units (e.g., '1' for 1 WETH)",
    )
    receiver: str = Field(
        ..., description="The address to receive the withdrawn assets"
    )


class MorphoWithdraw(MorphoBaseTool):
    """Withdraw assets from a Morpho Vault.

    This tool withdraws assets from a Morpho Vault by burning vault shares.
    """

    name: str = "morpho_withdraw"
    description: str = """Withdraw assets from a Morpho Vault.

Inputs:
- vault_address: The address of the Morpho Vault to withdraw from
- assets: The amount of assets to withdraw in whole units (e.g., '1' for 1 WETH)
- receiver: The address to receive the withdrawn assets

Important notes:
- Make sure you have enough shares in the vault to cover the withdrawal.
- The assets amount should be in whole units (e.g., '1' for 1 token, '0.5' for 0.5 tokens).
"""
    args_schema: ArgsSchema | None = WithdrawInput

    async def _arun(
        self,
        vault_address: str,
        assets: str,
        receiver: str,
    ) -> str:
        """Withdraw assets from a Morpho Vault.

        Args:
            vault_address: The address of the Morpho Vault.
            assets: The amount of assets to withdraw in whole units.
            receiver: The address to receive the assets.

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
            checksum_receiver = w3.to_checksum_address(receiver)

            # Convert assets to atomic units (assuming 18 decimals for simplicity)
            # In a production environment, you'd want to query the token decimals
            atomic_assets = int(assets_decimal * Decimal(10**18))

            # Encode withdraw function
            # withdraw(uint256 assets, address receiver, address owner)
            morpho_contract = w3.eth.contract(
                address=checksum_vault, abi=METAMORPHO_ABI
            )
            withdraw_data = morpho_contract.encode_abi(
                "withdraw",
                [atomic_assets, checksum_receiver, checksum_receiver],
            )

            # Send withdraw transaction
            tx_hash = await wallet.send_transaction(
                to=checksum_vault,
                data=withdraw_data,
            )

            # Wait for receipt
            await wallet.wait_for_transaction_receipt(tx_hash)

            return (
                f"Withdrawn {assets} from Morpho Vault {vault_address}\n"
                f"Receiver: {receiver}\n"
                f"Transaction hash: {tx_hash}"
            )

        except Exception as e:
            return f"Error withdrawing from Morpho Vault: {e!s}"
