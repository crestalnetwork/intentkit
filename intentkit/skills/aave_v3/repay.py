"""Aave V3 repay skill — repay borrowed tokens."""

import asyncio
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.aave_v3.base import AaveV3BaseTool
from intentkit.skills.aave_v3.constants import MAX_UINT256, POOL_ABI, POOL_ADDRESSES
from intentkit.skills.aave_v3.utils import (
    convert_amount,
    ensure_allowance,
    get_decimals,
    get_token_symbol,
)

NAME = "aave_v3_repay"


class RepayInput(BaseModel):
    """Input for Aave V3 repay."""

    token_address: str = Field(description="ERC20 token contract address to repay")
    amount: str = Field(
        description="Amount to repay in human-readable units (e.g. '100'), or 'max' to repay full debt"
    )
    interest_rate_mode: int = Field(
        default=2,
        description="Interest rate mode of the debt: 1 for stable, 2 for variable. Default: 2 (variable)",
    )


class AaveV3Repay(AaveV3BaseTool):
    """Repay borrowed tokens on Aave V3."""

    name: str = NAME
    description: str = (
        "Repay borrowed tokens on Aave V3. "
        "Use 'max' as amount to repay the full outstanding debt. "
        "Default interest rate mode is variable (2)."
    )
    args_schema: ArgsSchema | None = RepayInput

    @override
    async def _arun(
        self,
        token_address: str,
        amount: str,
        interest_rate_mode: int = 2,
        **kwargs: Any,
    ) -> str:
        try:
            chain_id = self._resolve_chain_id()

            if interest_rate_mode not in (1, 2):
                raise ToolException(
                    "interest_rate_mode must be 1 (stable) or 2 (variable)"
                )

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

            if amount.lower() == "max":
                amount_raw = MAX_UINT256
                approve_amount = MAX_UINT256
                amount_display = "max"
            else:
                amount_raw = convert_amount(amount, decimals)
                approve_amount = amount_raw
                amount_display = amount

            await ensure_allowance(
                w3, wallet, checksum_token, checksum_pool, approve_amount
            )

            pool = w3.eth.contract(address=checksum_pool, abi=POOL_ABI)
            repay_data = pool.encode_abi(
                "repay",
                [checksum_token, amount_raw, interest_rate_mode, wallet_address],
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_pool,
                data=repay_data,
            )

            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Repay transaction failed. Hash: {tx_hash}")

            rate_mode_str = "stable" if interest_rate_mode == 1 else "variable"

            return (
                f"**Aave V3 Repay**\n"
                f"Repaid: {amount_display} {symbol}\n"
                f"Rate Mode: {rate_mode_str}\n"
                f"Network: {self.get_agent_network_id()}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Repay failed: {e!s}")
