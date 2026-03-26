"""Aave V3 supply skill — deposit tokens into Aave as collateral."""

import asyncio
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.aave_v3.base import AaveV3BaseTool
from intentkit.skills.aave_v3.constants import POOL_ABI, POOL_ADDRESSES
from intentkit.skills.aave_v3.utils import (
    convert_amount,
    ensure_allowance,
    get_decimals,
    get_token_symbol,
)

NAME = "aave_v3_supply"


class SupplyInput(BaseModel):
    """Input for Aave V3 supply."""

    token_address: str = Field(description="ERC20 token contract address to supply")
    amount: str = Field(
        description="Amount in human-readable units (e.g. '100' for 100 USDC)"
    )


class AaveV3Supply(AaveV3BaseTool):
    """Supply (deposit) tokens into Aave V3 as collateral."""

    name: str = NAME
    description: str = (
        "Supply (deposit) tokens into Aave V3 lending protocol. "
        "The supplied tokens earn interest and can be used as collateral for borrowing. "
        "Provide the token contract address and amount in human-readable format."
    )
    args_schema: ArgsSchema | None = SupplyInput

    @override
    async def _arun(
        self,
        token_address: str,
        amount: str,
        **kwargs: Any,
    ) -> str:
        try:
            chain_id = self._resolve_chain_id()
            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()

            pool_address = POOL_ADDRESSES[chain_id]
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_pool = Web3.to_checksum_address(pool_address)
            wallet_address = Web3.to_checksum_address(wallet.address)

            decimals, symbol = await asyncio.gather(
                get_decimals(w3, checksum_token, chain_id),
                get_token_symbol(w3, checksum_token, chain_id),
            )
            amount_raw = convert_amount(amount, decimals)

            await ensure_allowance(
                w3, wallet, checksum_token, checksum_pool, amount_raw
            )

            pool = w3.eth.contract(address=checksum_pool, abi=POOL_ABI)
            supply_data = pool.encode_abi(
                "supply",
                [checksum_token, amount_raw, wallet_address, 0],
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_pool,
                data=supply_data,
            )

            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Supply transaction failed. Hash: {tx_hash}")

            return (
                f"**Aave V3 Supply**\n"
                f"Supplied: {amount} {symbol}\n"
                f"Network: {self.get_agent_network_id()}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Supply failed: {e!s}")
