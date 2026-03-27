"""Morpho deposit skill - Deposit assets into a Morpho Vault."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import METAMORPHO_ABI


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

    @override
    async def _arun(
        self,
        vault_address: str,
        token_address: str,
        assets: str,
        receiver: str,
        **kwargs: Any,
    ) -> str:
        try:
            wallet = await self.get_unified_wallet()
            self._validate_network(wallet.network_id)
            w3 = self.web3_client()

            assets_decimal = Decimal(assets)
            if assets_decimal <= Decimal("0"):
                raise ToolException("Error: Assets amount must be greater than 0")

            checksum_vault = w3.to_checksum_address(vault_address)
            checksum_token = w3.to_checksum_address(token_address)
            checksum_receiver = w3.to_checksum_address(receiver)

            token_contract = w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
            decimals = await token_contract.functions.decimals().call()
            atomic_assets = int(assets_decimal * (10**decimals))

            approve_data = token_contract.encode_abi(
                "approve", [checksum_vault, atomic_assets]
            )
            approve_tx_hash = await wallet.send_transaction(
                to=checksum_token,
                data=approve_data,
            )
            receipt = await wallet.wait_for_receipt(approve_tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(
                    f"Error: Approval transaction failed. Hash: {approve_tx_hash}"
                )

            morpho_contract = w3.eth.contract(
                address=checksum_vault, abi=METAMORPHO_ABI
            )
            deposit_data = morpho_contract.encode_abi(
                "deposit", [atomic_assets, checksum_receiver]
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_vault,
                data=deposit_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Deposit transaction failed. Hash: {tx_hash}")

            return (
                f"Deposited {assets} to Morpho Vault {vault_address}\n"
                f"Receiver: {receiver}\n"
                f"Transaction hash: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Error depositing to Morpho Vault: {e!s}")
