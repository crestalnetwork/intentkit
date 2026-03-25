"""Aerodrome Slipstream remove liquidity skill — decrease/remove a CL position."""

import time
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.models.skill import AgentSkillData
from intentkit.skills.aerodrome.base import AerodromeBaseTool
from intentkit.skills.aerodrome.constants import (
    CL_GAUGE_ABI,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESS,
    SKILL_DATA_NAMESPACE,
    STAKED_DATA_KEY,
)
from intentkit.skills.aerodrome.utils import format_amount, get_token_symbol

NAME = "aerodrome_remove_liquidity"

UINT128_MAX = (1 << 128) - 1


class AerodromeRemoveLiquidityInput(BaseModel):
    """Input for Aerodrome remove liquidity."""

    token_id: int = Field(description="NFT position ID to remove liquidity from")
    percentage: float = Field(
        default=100.0,
        description="Percentage of liquidity to remove (1-100)",
    )
    slippage: float = Field(
        default=0.5,
        description="Slippage tolerance in percent (e.g. 0.5 for 0.5%)",
    )


class AerodromeRemoveLiquidity(AerodromeBaseTool):
    """Remove liquidity from an Aerodrome Slipstream position on Base."""

    name: str = NAME
    description: str = (
        "Remove liquidity from an Aerodrome Slipstream position. "
        "Auto-unstakes from gauge if staked, harvesting AERO rewards. "
        "Specify percentage (1-100) to partially or fully remove."
    )
    args_schema: ArgsSchema | None = AerodromeRemoveLiquidityInput

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
                    f"Aerodrome is only supported on Base. "
                    f"Current network: {network_id}"
                )

            if not 1 <= percentage <= 100:
                raise ToolException("Percentage must be between 1 and 100")

            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()
            wallet_address = Web3.to_checksum_address(wallet.address)

            pm_address = Web3.to_checksum_address(POSITION_MANAGER_ADDRESS)
            pm = w3.eth.contract(address=pm_address, abi=POSITION_MANAGER_ABI)

            # Check if staked and unstake if needed
            aero_reward = 0
            was_staked = False

            staked_data = await self.get_agent_skill_data_raw(
                SKILL_DATA_NAMESPACE, STAKED_DATA_KEY
            )
            if staked_data and token_id in staked_data.get("token_ids", []):
                gauges = staked_data.get("gauges", {})
                gauge_address = gauges.get(str(token_id))
                if gauge_address:
                    was_staked = True
                    checksum_gauge = Web3.to_checksum_address(gauge_address)
                    gauge = w3.eth.contract(address=checksum_gauge, abi=CL_GAUGE_ABI)

                    # Get pending AERO before withdraw
                    try:
                        aero_reward = await gauge.functions.earned(
                            wallet_address, token_id
                        ).call()
                    except Exception:
                        pass

                    # Withdraw from gauge (returns NFT to wallet)
                    withdraw_data = gauge.encode_abi("withdraw", [token_id])
                    tx_hash = await wallet.send_transaction(
                        to=checksum_gauge,
                        data=withdraw_data,
                    )
                    receipt = await wallet.wait_for_receipt(tx_hash)
                    if receipt.get("status", 0) != 1:
                        raise ToolException(f"Gauge unstake failed. Hash: {tx_hash}")

                    # Remove from persisted staked list
                    await self._remove_staked_token_id(token_id)

            # Get position details
            pos_info = await pm.functions.positions(token_id).call()
            liquidity = pos_info[7]
            token0 = pos_info[2]
            token1 = pos_info[3]
            tick_spacing_val = pos_info[4]

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
            sym0 = await get_token_symbol(w3, token0)
            sym1 = await get_token_symbol(w3, token1)

            lines = [
                "**Liquidity Removed**",
                f"Position ID: {token_id}",
                f"Pool: {sym0}/{sym1} (tick spacing: {tick_spacing_val})",
                f"Removed: {percentage}% of liquidity",
            ]

            if was_staked:
                aero_human = format_amount(aero_reward, 18)
                lines.append(f"AERO rewards harvested: {aero_human}")

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
        staked_data = await self.get_agent_skill_data_raw(
            SKILL_DATA_NAMESPACE, STAKED_DATA_KEY
        )
        if staked_data and "token_ids" in staked_data:
            token_ids = [tid for tid in staked_data["token_ids"] if tid != token_id]
            gauges = staked_data.get("gauges", {})
            gauges.pop(str(token_id), None)
            if token_ids:
                await self.save_agent_skill_data_raw(
                    SKILL_DATA_NAMESPACE,
                    STAKED_DATA_KEY,
                    {"token_ids": token_ids, "gauges": gauges},
                )
            else:
                context = self.get_context()
                await AgentSkillData.delete(
                    context.agent_id, SKILL_DATA_NAMESPACE, STAKED_DATA_KEY
                )
