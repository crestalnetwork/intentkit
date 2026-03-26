"""Aave V3 get reserve data skill — read-only query of market/reserve info."""

import asyncio
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.aave_v3.base import AaveV3BaseTool
from intentkit.skills.aave_v3.constants import (
    POOL_DATA_PROVIDER_ABI,
    POOL_DATA_PROVIDER_ADDRESSES,
)
from intentkit.skills.aave_v3.utils import format_amount, format_ray, get_token_symbol

NAME = "aave_v3_get_reserve_data"


class GetReserveDataInput(BaseModel):
    """Input for getting Aave V3 reserve data."""

    token_address: str = Field(
        description="ERC20 token contract address of the reserve/market to query"
    )


class AaveV3GetReserveData(AaveV3BaseTool):
    """Get reserve/market data from Aave V3 including APY rates and liquidity."""

    name: str = NAME
    description: str = (
        "Get Aave V3 reserve/market data: supply APY, borrow APY, "
        "total supplied, total borrowed, and reserve configuration. "
        "Provide the token contract address."
    )
    args_schema: ArgsSchema | None = GetReserveDataInput

    @override
    async def _arun(
        self,
        token_address: str,
        **kwargs: Any,
    ) -> str:
        try:
            chain_id = self._resolve_chain_id()
            provider_address = POOL_DATA_PROVIDER_ADDRESSES[chain_id]
            w3 = self.web3_client()
            checksum_token = Web3.to_checksum_address(token_address)

            provider = w3.eth.contract(
                address=Web3.to_checksum_address(provider_address),
                abi=POOL_DATA_PROVIDER_ABI,
            )

            # Run all three independent RPC calls concurrently
            reserve_data, config_data, symbol = await asyncio.gather(
                provider.functions.getReserveData(checksum_token).call(),
                provider.functions.getReserveConfigurationData(checksum_token).call(),
                get_token_symbol(w3, checksum_token, chain_id),
            )

            (
                _unbacked,
                _accrued_to_treasury,
                total_atoken,
                total_stable_debt,
                total_variable_debt,
                liquidity_rate,
                variable_borrow_rate,
                stable_borrow_rate,
                _avg_stable_rate,
                _liquidity_index,
                _variable_borrow_index,
                _last_update,
            ) = reserve_data

            (
                decimals,
                ltv,
                liq_threshold,
                liq_bonus,
                reserve_factor,
                collateral_enabled,
                borrowing_enabled,
                stable_borrow_enabled,
                is_active,
                is_frozen,
            ) = config_data

            total_supplied = format_amount(total_atoken, decimals)
            total_borrowed = format_amount(
                total_stable_debt + total_variable_debt, decimals
            )

            status_parts = []
            if not is_active:
                status_parts.append("Inactive")
            if is_frozen:
                status_parts.append("Frozen")
            if not status_parts:
                status_parts.append("Active")
            status = ", ".join(status_parts)

            return (
                f"**Aave V3 Reserve Data — {symbol}** ({self.get_agent_network_id()})\n"
                f"Status: {status}\n"
                f"Supply APY: {format_ray(liquidity_rate)}\n"
                f"Variable Borrow APY: {format_ray(variable_borrow_rate)}\n"
                f"Stable Borrow APY: {format_ray(stable_borrow_rate)}\n"
                f"Total Supplied: {total_supplied} {symbol}\n"
                f"Total Borrowed: {total_borrowed} {symbol}\n"
                f"LTV: {ltv / 100:.2f}%\n"
                f"Liquidation Threshold: {liq_threshold / 100:.2f}%\n"
                f"Liquidation Bonus: {liq_bonus / 100:.2f}%\n"
                f"Reserve Factor: {reserve_factor / 100:.2f}%\n"
                f"Collateral Enabled: {collateral_enabled}\n"
                f"Borrowing Enabled: {borrowing_enabled}\n"
                f"Stable Borrow Enabled: {stable_borrow_enabled}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to get reserve data: {e!s}")
