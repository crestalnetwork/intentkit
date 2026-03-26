"""Aave V3 borrow skill — borrow tokens against collateral."""

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
    get_decimals,
    get_token_symbol,
)

NAME = "aave_v3_borrow"


class BorrowInput(BaseModel):
    """Input for Aave V3 borrow."""

    token_address: str = Field(description="ERC20 token contract address to borrow")
    amount: str = Field(
        description="Amount to borrow in human-readable units (e.g. '1000' for 1000 USDC)"
    )
    interest_rate_mode: int = Field(
        default=2,
        description="Interest rate mode: 1 for stable (if available), 2 for variable. Default: 2 (variable)",
    )


class AaveV3Borrow(AaveV3BaseTool):
    """Borrow tokens from Aave V3 against supplied collateral."""

    name: str = NAME
    description: str = (
        "Borrow tokens from Aave V3 against your supplied collateral. "
        "You must have sufficient collateral and health factor to borrow. "
        "Default interest rate mode is variable (2). Stable rate (1) is disabled on most markets."
    )
    args_schema: ArgsSchema | None = BorrowInput

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
            amount_raw = convert_amount(amount, decimals)

            # No approval needed — Aave mints debt tokens to the borrower
            pool = w3.eth.contract(address=checksum_pool, abi=POOL_ABI)
            borrow_data = pool.encode_abi(
                "borrow",
                [checksum_token, amount_raw, interest_rate_mode, 0, wallet_address],
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_pool,
                data=borrow_data,
            )

            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Borrow transaction failed. Hash: {tx_hash}")

            rate_mode_str = "stable" if interest_rate_mode == 1 else "variable"

            return (
                f"**Aave V3 Borrow**\n"
                f"Borrowed: {amount} {symbol}\n"
                f"Rate Mode: {rate_mode_str}\n"
                f"Network: {self.get_agent_network_id()}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Borrow failed: {e!s}")
