"""PancakeSwap V3 get positions skill — view liquidity positions."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools.base import ToolException
from web3 import Web3

from intentkit.skills.pancakeswap.base import PancakeSwapBaseTool
from intentkit.skills.pancakeswap.constants import (
    MASTERCHEF_V3_ABI,
    MASTERCHEF_V3_ADDRESSES,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESS,
)
from intentkit.skills.pancakeswap.utils import get_decimals, get_token_symbol

NAME = "pancakeswap_get_positions"
MAX_POSITIONS = 20


class PancakeSwapGetPositions(PancakeSwapBaseTool):
    """View PancakeSwap V3 liquidity positions."""

    name: str = NAME
    description: str = (
        "View your PancakeSwap V3 liquidity positions including pool details, "
        "liquidity amounts, uncollected fees, and farming status."
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
                    f"PancakeSwap not supported on {network_id}. "
                    f"Supported: {', '.join(NETWORK_TO_CHAIN_ID.keys())}"
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
                entry = await _format_position(
                    w3, chain_id, token_id, pos_info, staked=False
                )
                if entry:
                    positions.append(entry)

            # Get staked positions from persisted data
            masterchef_addr = MASTERCHEF_V3_ADDRESSES.get(chain_id)
            if masterchef_addr:
                staked_data = await self.get_agent_skill_data("staked_token_ids")
                if staked_data and "token_ids" in staked_data:
                    mc = w3.eth.contract(
                        address=Web3.to_checksum_address(masterchef_addr),
                        abi=MASTERCHEF_V3_ABI,
                    )
                    for token_id in staked_data["token_ids"][:MAX_POSITIONS]:
                        try:
                            user_info = await mc.functions.userPositionInfos(
                                token_id
                            ).call()
                            # user_info[6] is the user address
                            if user_info[6].lower() != wallet_address.lower():
                                continue
                            pos_info = await pm.functions.positions(token_id).call()
                            pending_cake = await mc.functions.pendingCake(
                                token_id
                            ).call()
                            entry = await _format_position(
                                w3,
                                chain_id,
                                token_id,
                                pos_info,
                                staked=True,
                                pending_cake=pending_cake,
                            )
                            if entry:
                                positions.append(entry)
                        except Exception:
                            continue

            if not positions:
                return "No active PancakeSwap V3 liquidity positions found."

            header = f"**PancakeSwap V3 Positions** ({len(positions)} found)\n\n"
            return header + "\n---\n".join(positions)

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to get positions: {e!s}")


async def _format_position(
    w3: Any,
    chain_id: int,
    token_id: int,
    pos_info: tuple[Any, ...],
    staked: bool = False,
    pending_cake: int = 0,
) -> str | None:
    """Format a single position for display."""
    # pos_info: (nonce, operator, token0, token1, fee, tickLower, tickUpper,
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
    fee = pos_info[4]
    tick_lower = pos_info[5]
    tick_upper = pos_info[6]

    sym0 = await get_token_symbol(w3, token0, chain_id)
    sym1 = await get_token_symbol(w3, token1, chain_id)
    dec0 = await get_decimals(w3, token0, chain_id)
    dec1 = await get_decimals(w3, token1, chain_id)

    fee_pct = Decimal(fee) / Decimal(10000)
    fees0 = Decimal(tokens_owed0) / Decimal(10**dec0)
    fees1 = Decimal(tokens_owed1) / Decimal(10**dec1)

    lines = [
        f"**Position #{token_id}**",
        f"Pool: {sym0}/{sym1} ({fee_pct}%)",
        f"Tick range: [{tick_lower}, {tick_upper}]",
        f"Liquidity: {liquidity}",
        f"Uncollected fees: {fees0:.8f} {sym0}, {fees1:.8f} {sym1}",
    ]

    if staked:
        cake_amount = Decimal(pending_cake) / Decimal(10**18)
        lines.append(f"Farming: Staked | Pending CAKE: {cake_amount:.6f}")
    else:
        lines.append("Farming: Not staked")

    return "\n".join(lines)
