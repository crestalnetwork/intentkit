"""Aave V3 withdraw skill — withdraw supplied tokens."""

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
    get_decimals,
    get_token_symbol,
)

NAME = "aave_v3_withdraw"


class WithdrawInput(BaseModel):
    """Input for Aave V3 withdraw."""

    token_address: str = Field(description="ERC20 token contract address to withdraw")
    amount: str = Field(
        description="Amount in human-readable units (e.g. '100'), or 'max' to withdraw all"
    )


class AaveV3Withdraw(AaveV3BaseTool):
    """Withdraw supplied tokens from Aave V3."""

    name: str = NAME
    description: str = (
        "Withdraw supplied tokens from Aave V3. "
        "Use 'max' as amount to withdraw the entire supplied balance. "
        "Note: withdrawing may affect your health factor if used as collateral."
    )
    args_schema: ArgsSchema | None = WithdrawInput

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

            if amount.lower() == "max":
                amount_raw = MAX_UINT256
                amount_display = "all (max)"
            else:
                amount_raw = convert_amount(amount, decimals)
                amount_display = amount

            pool = w3.eth.contract(address=checksum_pool, abi=POOL_ABI)
            withdraw_data = pool.encode_abi(
                "withdraw",
                [checksum_token, amount_raw, wallet_address],
            )

            tx_hash = await wallet.send_transaction(
                to=checksum_pool,
                data=withdraw_data,
            )

            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Withdraw transaction failed. Hash: {tx_hash}")

            return (
                f"**Aave V3 Withdraw**\n"
                f"Withdrawn: {amount_display} {symbol}\n"
                f"Network: {self.get_agent_network_id()}\n"
                f"Tx: {tx_hash}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Withdraw failed: {e!s}")
