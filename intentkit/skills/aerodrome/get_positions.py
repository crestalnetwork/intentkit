"""Aerodrome Slipstream get positions skill — view CL liquidity positions."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools.base import ToolException
from web3 import Web3

from intentkit.skills.aerodrome.base import AerodromeBaseTool
from intentkit.skills.aerodrome.constants import (
    CL_GAUGE_ABI,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESS,
    SKILL_DATA_NAMESPACE,
    STAKED_DATA_KEY,
)
from intentkit.skills.aerodrome.utils import get_decimals, get_token_symbol

NAME = "aerodrome_get_positions"
MAX_POSITIONS = 20


class AerodromeGetPositions(AerodromeBaseTool):
    """View Aerodrome Slipstream liquidity positions on Base."""

    name: str = NAME
    description: str = (
        "View your Aerodrome Slipstream liquidity positions on Base including "
        "pool details, liquidity amounts, uncollected fees, and farming status."
    )

    @override
    async def _arun(self, **kwargs: Any) -> str:
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

            wallet = await self.get_unified_wallet()
            w3 = self.web3_client()
            wallet_address = Web3.to_checksum_address(wallet.address)

            pm = w3.eth.contract(
                address=Web3.to_checksum_address(POSITION_MANAGER_ADDRESS),
                abi=POSITION_MANAGER_ABI,
            )

            # Get unstaked positions
            balance = await pm.functions.balanceOf(wallet_address).call()
            positions: list[str] = []

            count = min(balance, MAX_POSITIONS)
            for i in range(count):
                token_id = await pm.functions.tokenOfOwnerByIndex(
                    wallet_address, i
                ).call()
                pos_info = await pm.functions.positions(token_id).call()
                entry = await _format_position(w3, token_id, pos_info, staked=False)
                if entry:
                    positions.append(entry)

            staked_data = await self.get_agent_skill_data_raw(
                SKILL_DATA_NAMESPACE, STAKED_DATA_KEY
            )
            if staked_data and "token_ids" in staked_data:
                gauges = staked_data.get("gauges", {})
                for token_id in staked_data["token_ids"][:MAX_POSITIONS]:
                    try:
                        gauge_address = gauges.get(str(token_id))
                        if not gauge_address:
                            continue

                        checksum_gauge = Web3.to_checksum_address(gauge_address)
                        gauge = w3.eth.contract(
                            address=checksum_gauge, abi=CL_GAUGE_ABI
                        )

                        is_staked = await gauge.functions.stakedContains(
                            wallet_address, token_id
                        ).call()
                        if not is_staked:
                            continue

                        pos_info = await pm.functions.positions(token_id).call()
                        pending_aero = await gauge.functions.earned(
                            wallet_address, token_id
                        ).call()
                        entry = await _format_position(
                            w3,
                            token_id,
                            pos_info,
                            staked=True,
                            pending_aero=pending_aero,
                        )
                        if entry:
                            positions.append(entry)
                    except Exception:
                        continue

            if not positions:
                return "No active Aerodrome Slipstream liquidity positions found."

            header = f"**Aerodrome Slipstream Positions** ({len(positions)} found)\n\n"
            return header + "\n---\n".join(positions)

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to get positions: {e!s}")


async def _format_position(
    w3: Any,
    token_id: int,
    pos_info: tuple[Any, ...],
    staked: bool = False,
    pending_aero: int = 0,
) -> str | None:
    """Format a single position for display."""
    # pos_info: (nonce, operator, token0, token1, tickSpacing, tickLower, tickUpper,
    #            liquidity, feeGrowthInside0LastX128, feeGrowthInside1LastX128,
    #            tokensOwed0, tokensOwed1)
    liquidity = pos_info[7]
    tokens_owed0 = pos_info[10]
    tokens_owed1 = pos_info[11]

    # Skip empty positions with no fees
    if liquidity == 0 and tokens_owed0 == 0 and tokens_owed1 == 0:
        return None

    token0 = pos_info[2]
    token1 = pos_info[3]
    tick_spacing_val = pos_info[4]
    tick_lower = pos_info[5]
    tick_upper = pos_info[6]

    sym0 = await get_token_symbol(w3, token0)
    sym1 = await get_token_symbol(w3, token1)
    dec0 = await get_decimals(w3, token0)
    dec1 = await get_decimals(w3, token1)

    fees0 = Decimal(tokens_owed0) / Decimal(10**dec0)
    fees1 = Decimal(tokens_owed1) / Decimal(10**dec1)

    lines = [
        f"**Position #{token_id}**",
        f"Pool: {sym0}/{sym1} (tick spacing: {tick_spacing_val})",
        f"Tick range: [{tick_lower}, {tick_upper}]",
        f"Liquidity: {liquidity}",
        f"Uncollected fees: {fees0:.8f} {sym0}, {fees1:.8f} {sym1}",
    ]

    if staked:
        aero_amount = Decimal(pending_aero) / Decimal(10**18)
        lines.append(f"Farming: Staked | Pending AERO: {aero_amount:.6f}")
    else:
        lines.append("Farming: Not staked")

    return "\n".join(lines)
