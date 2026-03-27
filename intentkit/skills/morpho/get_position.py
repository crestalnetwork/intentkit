"""Morpho get position skill — read-only query of user position in a Morpho Blue market."""

import asyncio
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.constants import (
    MORPHO_BLUE_ABI,
    MORPHO_BLUE_ADDRESS,
)


class GetPositionInput(BaseModel):
    """Input for getting Morpho Blue position."""

    market_id: str = Field(description="Morpho Blue market ID (bytes32 hex string)")
    user_address: str | None = Field(
        default=None,
        description="Address to query. Defaults to agent's own wallet address if not provided.",
    )


class MorphoGetPosition(MorphoBaseTool):
    """Get user position in a Morpho Blue market."""

    name: str = "morpho_get_position"
    description: str = (
        "Get user position in a Morpho Blue market: supply shares, borrow shares, "
        "collateral amount, and market totals. Provide the market ID (bytes32). "
        "Defaults to querying the agent's own wallet."
    )
    args_schema: ArgsSchema | None = GetPositionInput

    @override
    async def _arun(
        self,
        market_id: str,
        user_address: str | None = None,
        **kwargs: Any,
    ) -> str:
        try:
            wallet = await self.get_unified_wallet()
            self._validate_network(wallet.network_id)
            w3 = self.web3_client()

            checksum_morpho = Web3.to_checksum_address(MORPHO_BLUE_ADDRESS)
            morpho = w3.eth.contract(address=checksum_morpho, abi=MORPHO_BLUE_ABI)

            if user_address:
                query_address = Web3.to_checksum_address(user_address)
            else:
                query_address = Web3.to_checksum_address(wallet.address)

            market_id_bytes = self._parse_market_id(market_id)

            position_data, market_data, params = await asyncio.gather(
                morpho.functions.position(market_id_bytes, query_address).call(),
                morpho.functions.market(market_id_bytes).call(),
                morpho.functions.idToMarketParams(market_id_bytes).call(),
            )

            supply_shares, borrow_shares, collateral = position_data
            (
                total_supply_assets,
                total_supply_shares,
                total_borrow_assets,
                total_borrow_shares,
                _last_update,
                _fee,
            ) = market_data
            loan_token, collateral_token, _oracle, _irm, lltv = params

            if loan_token == "0x0000000000000000000000000000000000000000":
                raise ToolException(
                    f"Error: Market {market_id} does not exist on Morpho Blue"
                )

            loan_contract = w3.eth.contract(
                address=Web3.to_checksum_address(loan_token), abi=ERC20_ABI
            )
            collateral_contract = w3.eth.contract(
                address=Web3.to_checksum_address(collateral_token), abi=ERC20_ABI
            )
            (
                loan_decimals,
                loan_symbol,
                collateral_decimals,
                collateral_symbol,
            ) = await asyncio.gather(
                loan_contract.functions.decimals().call(),
                loan_contract.functions.symbol().call(),
                collateral_contract.functions.decimals().call(),
                collateral_contract.functions.symbol().call(),
            )

            if total_supply_shares > 0:
                user_supply_assets = (
                    supply_shares * total_supply_assets // total_supply_shares
                )
            else:
                user_supply_assets = 0

            if total_borrow_shares > 0:
                user_borrow_assets = (
                    borrow_shares * total_borrow_assets // total_borrow_shares
                )
            else:
                user_borrow_assets = 0

            supply_formatted = Decimal(user_supply_assets) / Decimal(10**loan_decimals)
            borrow_formatted = Decimal(user_borrow_assets) / Decimal(10**loan_decimals)
            collateral_formatted = Decimal(collateral) / Decimal(
                10**collateral_decimals
            )
            lltv_pct = Decimal(lltv) / Decimal(10**18) * 100

            return (
                f"**Morpho Blue Position**\n"
                f"Market: {market_id}\n"
                f"User: {query_address}\n"
                f"Supply: {supply_formatted} {loan_symbol}\n"
                f"Borrow: {borrow_formatted} {loan_symbol}\n"
                f"Collateral: {collateral_formatted} {collateral_symbol}\n"
                f"LLTV: {lltv_pct:.2f}%\n"
                f"Network: {wallet.network_id}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to get position: {e!s}")
