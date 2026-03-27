"""Morpho withdraw skill - Withdraw assets from a Morpho Vault."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import METAMORPHO_ABI


class WithdrawInput(BaseModel):
    """Input schema for Morpho withdraw."""

    vault_address: str = Field(..., description="Morpho Vault address")
    assets: str = Field(
        ...,
        description="Amount in whole units (e.g. '1' for 1 WETH)",
    )
    receiver: str = Field(..., description="Address to receive withdrawn assets")


class MorphoWithdraw(MorphoBaseTool):
    """Withdraw assets from a Morpho Vault.

    This tool withdraws assets from a Morpho Vault by burning vault shares.
    """

    name: str = "morpho_withdraw"
    description: str = "Withdraw assets from a Morpho Vault. Ensure sufficient vault shares. Amount in whole units."
    args_schema: ArgsSchema | None = WithdrawInput

    @override
    async def _arun(
        self,
        vault_address: str,
        assets: str,
        receiver: str,
        **kwargs: Any,
    ) -> str:
        try:
            wallet = await self.get_unified_wallet()
            self._validate_network(wallet.network_id)
            w3 = self.web3_client()

            checksum_vault = w3.to_checksum_address(vault_address)
            checksum_receiver = w3.to_checksum_address(receiver)

            vault_contract = w3.eth.contract(address=checksum_vault, abi=METAMORPHO_ABI)
            asset_address = await vault_contract.functions.asset().call()

            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(asset_address), abi=ERC20_ABI
            )
            decimals = await token_contract.functions.decimals().call()

            assets_decimal = Decimal(assets)
            if assets_decimal <= Decimal("0"):
                raise ToolException("Error: Assets amount must be greater than 0")

            atomic_assets = int(assets_decimal * Decimal(10**decimals))

            withdraw_data = vault_contract.encode_abi(
                "withdraw",
                [atomic_assets, checksum_receiver, checksum_receiver],
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_vault,
                data=withdraw_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Withdraw transaction failed. Hash: {tx_hash}")

            return (
                f"Withdrawn {assets} from Morpho Vault {vault_address}\n"
                f"Receiver: {receiver}\n"
                f"Transaction hash: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Error withdrawing from Morpho Vault: {e!s}")
