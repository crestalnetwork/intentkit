"""Morpho get vault data skill — read-only query of MetaMorpho Vault info."""

import asyncio
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import METAMORPHO_ABI


class GetVaultDataInput(BaseModel):
    """Input for getting MetaMorpho Vault data."""

    vault_address: str = Field(description="MetaMorpho Vault contract address")


class MorphoGetVaultData(MorphoBaseTool):
    """Get MetaMorpho Vault data including total assets, share price, and underlying token."""

    name: str = "morpho_get_vault_data"
    description: str = (
        "Get MetaMorpho Vault info: total assets, total shares, "
        "share price, and underlying asset token. "
        "Provide the vault contract address."
    )
    args_schema: ArgsSchema | None = GetVaultDataInput

    @override
    async def _arun(
        self,
        vault_address: str,
        **kwargs: Any,
    ) -> str:
        try:
            wallet = await self.get_unified_wallet()
            self._validate_network(wallet.network_id)
            w3 = self.web3_client()

            checksum_vault = Web3.to_checksum_address(vault_address)
            vault_contract = w3.eth.contract(address=checksum_vault, abi=METAMORPHO_ABI)

            total_assets, asset_address, total_supply = await asyncio.gather(
                vault_contract.functions.totalAssets().call(),
                vault_contract.functions.asset().call(),
                vault_contract.functions.totalSupply().call(),
            )

            checksum_asset = Web3.to_checksum_address(asset_address)
            token_contract = w3.eth.contract(address=checksum_asset, abi=ERC20_ABI)
            decimals, symbol = await asyncio.gather(
                token_contract.functions.decimals().call(),
                token_contract.functions.symbol().call(),
            )

            one_share = 10**18
            if total_supply > 0:
                assets_per_share = await vault_contract.functions.convertToAssets(
                    one_share
                ).call()
                share_price = Decimal(assets_per_share) / Decimal(10**decimals)
            else:
                share_price = Decimal("1")

            total_assets_formatted = Decimal(total_assets) / Decimal(10**decimals)

            return (
                f"**MetaMorpho Vault Data**\n"
                f"Vault: {vault_address}\n"
                f"Underlying Asset: {symbol} ({asset_address})\n"
                f"Total Assets: {total_assets_formatted} {symbol}\n"
                f"Total Shares: {Decimal(total_supply) / Decimal(10**18)}\n"
                f"Share Price: 1 share = {share_price} {symbol}\n"
                f"Network: {wallet.network_id}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to get vault data: {e!s}")
