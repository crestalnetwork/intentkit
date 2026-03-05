"""PancakeSwap V3 remove liquidity skill — decrease/remove a position."""

import time
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.pancakeswap.base import PancakeSwapBaseTool
from intentkit.skills.pancakeswap.constants import (
    MASTERCHEF_V3_ABI,
    MASTERCHEF_V3_ADDRESSES,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESS,
)
from intentkit.skills.pancakeswap.utils import (
    format_amount,
    get_token_symbol,
)

NAME = "pancakeswap_remove_liquidity"

UINT128_MAX = (1 << 128) - 1


class PancakeSwapRemoveLiquidityInput(BaseModel):
    """Input for PancakeSwap remove liquidity."""

    token_id: int = Field(description="NFT position ID to remove liquidity from")
    percentage: float = Field(
        default=100.0,
        description="Percentage of liquidity to remove (1-100)",
    )
    slippage: float = Field(
        default=0.5,
        description="Slippage tolerance in percent (e.g. 0.5 for 0.5%)",
    )


class PancakeSwapRemoveLiquidity(PancakeSwapBaseTool):
    """Remove liquidity from a PancakeSwap V3 position."""

    name: str = NAME
    description: str = (
        "Remove liquidity from a PancakeSwap V3 position. "
        "Auto-unstakes from MasterChef V3 farm if staked. "
        "Specify percentage (1-100) to partially or fully remove."
    )
    args_schema: ArgsSchema | None = PancakeSwapRemoveLiquidityInput

    @override
    async def _arun(
        self,
        token_id: int,
        percentage: float = 100.0,
        slippage: float = 0.5,
        **kwargs: Any,
    ) -> str:
        try:
            network_id = self.get_agent_network_id()
            if not network_id:
                raise ToolException("Agent network_id is not configured")

            chain_id = NETWORK_TO_CHAIN_ID.get(network_id)
            if not chain_id:
                raise ToolException(
                    f"PancakeSwap not supported on {network_id}. "
                    f"Supported: {', '.join(NETWORK_TO_CHAIN_ID.keys())}"
                )

            if not 1 <= percentage <= 100:
                raise ToolException("Percentage must be between 1 and 100")

            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()
            wallet_address = Web3.to_checksum_address(wallet.address)

            pm_address = Web3.to_checksum_address(POSITION_MANAGER_ADDRESS)
            pm = w3.eth.contract(address=pm_address, abi=POSITION_MANAGER_ABI)

            # Check if staked and unstake if needed
            cake_reward = 0
            masterchef_addr = MASTERCHEF_V3_ADDRESSES.get(chain_id)
            was_staked = False

            if masterchef_addr:
                checksum_mc = Web3.to_checksum_address(masterchef_addr)
                mc = w3.eth.contract(
                    address=checksum_mc,
                    abi=MASTERCHEF_V3_ABI,
                )
                try:
                    user_info = await mc.functions.userPositionInfos(token_id).call()
                    # user_info[6] is the user address
                    if user_info[6].lower() == wallet_address.lower():
                        was_staked = True
                        # Withdraw from MasterChef (also harvests CAKE)
                        withdraw_data = mc.encode_abi(
                            "withdraw", [token_id, wallet_address]
                        )
                        tx_hash = await wallet.send_transaction(
                            to=checksum_mc,
                            data=withdraw_data,
                        )
                        receipt = await wallet.wait_for_receipt(tx_hash)
                        if receipt.get("status", 0) != 1:
                            raise ToolException(f"Unstake failed. Hash: {tx_hash}")

                        # Get pending CAKE before withdraw for display
                        cake_reward = await mc.functions.pendingCake(token_id).call()

                        # Remove from persisted staked list
                        await self._remove_staked_token_id(token_id)
                except Exception:
                    if was_staked:
                        raise
                    # Not staked in MasterChef, continue
                    pass

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

            # Decrease liquidity
            decrease_data = pm.encode_abi(
                "decreaseLiquidity",
                [(token_id, liquidity_to_remove, 0, 0, deadline)],
            )
            tx_hash = await wallet.send_transaction(
                to=pm_address,
                data=decrease_data,
            )
            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Decrease liquidity failed. Hash: {tx_hash}")

            # Collect all tokens + fees
            collect_data = pm.encode_abi(
                "collect",
                [(token_id, wallet_address, UINT128_MAX, UINT128_MAX)],
            )
            tx_hash = await wallet.send_transaction(
                to=pm_address,
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
                        to=pm_address,
                        data=burn_data,
                    )
                    burn_receipt = await wallet.wait_for_receipt(burn_tx)
                    burned = burn_receipt.get("status", 0) == 1
                except Exception:
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

            if was_staked:
                cake_human = format_amount(cake_reward, 18)
                lines.append(f"CAKE rewards harvested: {cake_human}")

            if burned:
                lines.append("NFT burned: Yes")

            lines.append(f"Tx: {tx_hash}")
            return "\n".join(lines)

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Remove liquidity failed: {e!s}")

    async def _remove_staked_token_id(self, token_id: int) -> None:
        """Remove a token ID from the persisted staked list."""
        staked_data = await self.get_agent_skill_data("staked_token_ids")
        if staked_data and "token_ids" in staked_data:
            token_ids = [tid for tid in staked_data["token_ids"] if tid != token_id]
            if token_ids:
                await self.save_agent_skill_data(
                    "staked_token_ids", {"token_ids": token_ids}
                )
            else:
                await self.delete_agent_skill_data("staked_token_ids")
