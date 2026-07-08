"""Aave V3 get user account data tool — read-only query of user position."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.aave_v3.base import AaveV3BaseTool
from intentkit.tools.aave_v3.constants import POOL_ABI, POOL_ADDRESSES
from intentkit.tools.aave_v3.utils import format_base_currency, format_health_factor
from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION
from intentkit.wallets.web3 import get_async_web3_client

NAME = "aave_v3_get_user_account_data"


class GetUserAccountDataInput(BaseModel):
    """Input for getting Aave V3 user account data."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)
    user_address: str | None = Field(
        default=None,
        description="Address to query. Defaults to the wallet_address argument.",
    )


class AaveV3GetUserAccountData(AaveV3BaseTool):
    """Get user account data from Aave V3 including health factor and positions."""

    name: str = NAME
    title: str = "Get Account Data"
    description: str = (
        "Get Aave V3 account overview: total collateral, total debt, "
        "available borrows, health factor, and LTV."
    )
    args_schema: ArgsSchema | None = GetUserAccountDataInput

    @override
    async def _arun(
        self,
        wallet_address: str,
        user_address: str | None = None,
        **kwargs: Any,
    ) -> str:
        try:
            # Read-only: validate the wallet belongs to the team, no signing.
            # The wallet also determines the network to query.
            wallet = await self.resolve_wallet(wallet_address)
            network_id = wallet.network
            chain_id = self._resolve_chain_id(network_id)
            pool_address = POOL_ADDRESSES[chain_id]
            w3 = get_async_web3_client(network_id)

            query_address = Web3.to_checksum_address(user_address or wallet_address)

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
                f"**Aave V3 Account Data** ({network_id})\n"
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
