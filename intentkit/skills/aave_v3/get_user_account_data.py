"""Aave V3 get user account data skill — read-only query of user position."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.aave_v3.base import AaveV3BaseTool
from intentkit.skills.aave_v3.constants import POOL_ABI, POOL_ADDRESSES
from intentkit.skills.aave_v3.utils import format_base_currency, format_health_factor

NAME = "aave_v3_get_user_account_data"


class GetUserAccountDataInput(BaseModel):
    """Input for getting Aave V3 user account data."""

    user_address: str | None = Field(
        default=None,
        description="Address to query. Defaults to agent's own wallet address if not provided.",
    )


class AaveV3GetUserAccountData(AaveV3BaseTool):
    """Get user account data from Aave V3 including health factor and positions."""

    name: str = NAME
    description: str = (
        "Get Aave V3 account overview: total collateral, total debt, "
        "available borrows, health factor, and LTV. "
        "Defaults to querying the agent's own wallet."
    )
    args_schema: ArgsSchema | None = GetUserAccountDataInput

    @override
    async def _arun(
        self,
        user_address: str | None = None,
        **kwargs: Any,
    ) -> str:
        try:
            chain_id = self._resolve_chain_id()
            pool_address = POOL_ADDRESSES[chain_id]
            w3 = self.web3_client()

            if user_address:
                query_address = Web3.to_checksum_address(user_address)
            else:
                wallet = await self.get_unified_wallet()
                query_address = Web3.to_checksum_address(wallet.address)

            pool = w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=POOL_ABI,
            )

            result = await pool.functions.getUserAccountData(query_address).call()
            (
                total_collateral,
                total_debt,
                available_borrows,
                liquidation_threshold,
                ltv,
                health_factor,
            ) = result

            return (
                f"**Aave V3 Account Data** ({self.get_agent_network_id()})\n"
                f"Address: {query_address}\n"
                f"Total Collateral: {format_base_currency(total_collateral)}\n"
                f"Total Debt: {format_base_currency(total_debt)}\n"
                f"Available to Borrow: {format_base_currency(available_borrows)}\n"
                f"Liquidation Threshold: {liquidation_threshold / 100:.2f}%\n"
                f"LTV: {ltv / 100:.2f}%\n"
                f"Health Factor: {format_health_factor(health_factor)}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to get account data: {e!s}")
