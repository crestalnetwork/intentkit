"""Morpho deposit skill - Deposit assets into a Morpho Vault."""

from decimal import Decimal

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import METAMORPHO_ABI, SUPPORTED_NETWORKS


class DepositInput(BaseModel):
    """Input schema for Morpho deposit."""

    vault_address: str = Field(..., description="Morpho Vault address")
    token_address: str = Field(..., description="Token contract address to deposit")
    assets: str = Field(
        ...,
        description="Amount in whole units (e.g. '1' for 1 WETH)",
    )
    receiver: str = Field(..., description="Address to receive vault shares")


class MorphoDeposit(MorphoBaseTool):
    """Deposit assets into a Morpho Vault.

    This tool deposits assets into a Morpho Vault and receives shares
    representing the deposited amount.
    """

    name: str = "morpho_deposit"
    description: str = "Deposit assets into a Morpho Vault. Provide token_address as a contract address. Use exact amounts in whole units; do not convert."
    args_schema: ArgsSchema | None = DepositInput

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
                raise ToolException(
                    f"Error: Morpho is not supported on network {network_id}. "
                    f"Supported networks: {', '.join(SUPPORTED_NETWORKS)}"
                )

            # Validate assets amount
            assets_decimal = Decimal(assets)
            if assets_decimal <= Decimal("0"):
                raise ToolException("Error: Assets amount must be greater than 0")
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
                raise ToolException(
                    f"Error: Approval transaction failed. Hash: {approve_tx_hash}"
                )
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
            raise ToolException(f"Error depositing to Morpho Vault: {e!s}")
