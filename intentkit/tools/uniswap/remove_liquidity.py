"""Uniswap V3 remove liquidity tool — decrease/remove a position."""

import time
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION
from intentkit.tools.uniswap.base import UniswapBaseTool
from intentkit.tools.uniswap.constants import (
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESSES,
)
from intentkit.tools.uniswap.utils import get_token_symbol

NAME = "uniswap_remove_liquidity"

UINT128_MAX = (1 << 128) - 1


class UniswapRemoveLiquidityInput(BaseModel):
    """Input for Uniswap remove liquidity."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)
    token_id: int = Field(description="NFT position ID to remove liquidity from")
    percentage: float = Field(
        default=100.0,
        description="Percentage of liquidity to remove (1-100)",
    )


class UniswapRemoveLiquidity(UniswapBaseTool):
    """Remove liquidity from a Uniswap V3 position."""

    name: str = NAME
    title: str = "Remove Liquidity"
    team_only: bool = True
    description: str = (
        "Remove liquidity from a Uniswap V3 position. "
        "Specify percentage (1-100) to partially or fully remove."
    )
    args_schema: ArgsSchema | None = UniswapRemoveLiquidityInput

    @override
    async def _arun(
        self,
        wallet_address: str,
        token_id: int,
        percentage: float = 100.0,
        **kwargs: Any,
    ) -> str:
        try:
            wallet = await self.get_unified_wallet(wallet_address)
            chain_id = self._resolve_chain_id(wallet.network_id)

            if not 1 <= percentage <= 100:
                raise ToolException("Percentage must be between 1 and 100")

            pm_address = POSITION_MANAGER_ADDRESSES.get(chain_id)
            if not pm_address:
                raise ToolException(f"No PositionManager address for chain {chain_id}")

            w3 = wallet.w3
            recipient = Web3.to_checksum_address(wallet.address)

            checksum_pm = Web3.to_checksum_address(pm_address)
            pm = w3.eth.contract(address=checksum_pm, abi=POSITION_MANAGER_ABI)

            # Get position details
            pos_info = await pm.functions.positions(token_id).call()
            liquidity = pos_info[7]
            token0 = pos_info[2]
            token1 = pos_info[3]
            fee = pos_info[4]

            if liquidity == 0:
                raise ToolException(f"Position {token_id} has no liquidity to remove")

            # Calculate liquidity to remove
            liquidity_to_remove = int(liquidity * percentage / 100)
            is_full_removal = percentage == 100.0

            deadline = int(time.time()) + 600

            # Decrease liquidity (amount mins set to 0 — on-chain simulation
            # would be needed for proper slippage protection)
            decrease_data = pm.encode_abi(
                "decreaseLiquidity",
                [(token_id, liquidity_to_remove, 0, 0, deadline)],
            )
            tx_hash = await wallet.send_transaction(
                to=checksum_pm,
                data=decrease_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Decrease liquidity failed. Hash: {tx_hash}")

            # Collect all tokens + fees
            collect_data = pm.encode_abi(
                "collect",
                [(token_id, recipient, UINT128_MAX, UINT128_MAX)],
            )
            tx_hash = await wallet.send_transaction(
                to=checksum_pm,
                data=collect_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Collect failed. Hash: {tx_hash}")

            # Burn empty NFT on full removal
            burned = False
            if is_full_removal:
                try:
                    burn_data = pm.encode_abi("burn", [token_id])
                    burn_tx = await wallet.send_transaction(
                        to=checksum_pm,
                        data=burn_data,
                    )
                    burn_receipt = await wallet.wait_for_receipt(burn_tx)
                    burned = burn_receipt.get("status", 0) == 1
                except Exception:  # noqa: S110 - best-effort step; outcome is reflected in the result
                    pass

            # Format result
            sym0 = await get_token_symbol(w3, token0, chain_id)
            sym1 = await get_token_symbol(w3, token1, chain_id)
            fee_pct = Decimal(fee) / Decimal(10000)

            lines = [
                "**Liquidity Removed**",
                f"Position ID: {token_id}",
                f"Pool: {sym0}/{sym1} ({fee_pct}%)",
                f"Removed: {percentage}% of liquidity",
            ]

            if burned:
                lines.append("NFT burned: Yes")

            lines.append(f"Tx: {tx_hash}")
            return "\n".join(lines)

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Remove liquidity failed: {e!s}")
