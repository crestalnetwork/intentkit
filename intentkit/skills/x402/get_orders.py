"""x402 get orders skill.

This skill retrieves recent x402 payment orders for the current agent.
"""

import logging
from decimal import Decimal
from typing import override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.models.x402_order import X402Order
from intentkit.skills.x402.base import X402BaseSkill

logger = logging.getLogger(__name__)

# Asset decimals mapping (ERC-20 standard decimals)
ASSET_DECIMALS: dict[str, int] = {
    "USDC": 6,
    "USDT": 6,
    "DAI": 18,
    "WETH": 18,
    "ETH": 18,
}
DEFAULT_DECIMALS = 6


def format_amount(raw_amount: int, asset: str) -> str:
    """Format raw integer amount to human-readable decimal string.

    Args:
        raw_amount: Amount in base units (e.g., 1000000 for 1 USDC)
        asset: Asset symbol (e.g., "USDC")

    Returns:
        Formatted amount string (e.g., "1.0 USDC")
    """
    decimals = ASSET_DECIMALS.get(asset.upper(), DEFAULT_DECIMALS)
    divisor = Decimal(10**decimals)
    amount = Decimal(raw_amount) / divisor
    # Remove trailing zeros and format
    formatted = f"{amount:.{decimals}f}".rstrip("0").rstrip(".")
    return f"{formatted} {asset}"


class X402GetOrdersInput(BaseModel):
    """Arguments for getting x402 orders."""

    limit: int = Field(
        default=5,
        description="Maximum number of orders to retrieve (1-10). Default is 5.",
        ge=1,
        le=10,
    )


class X402GetOrders(X402BaseSkill):
    """Skill that retrieves recent successful x402 payment orders for the current agent."""

    name: str = "x402_get_orders"
    description: str = (
        "Retrieve recent successful x402 payment orders made by this agent. "
        "Returns the most recent orders including URL, description, amount, and transaction hash. "
        "Use this to review past payment activities."
    )
    args_schema: ArgsSchema | None = X402GetOrdersInput

    @override
    async def _arun(
        self,
        limit: int = 5,
    ) -> str:
        context = self.get_context()
        agent_id = context.agent_id

        orders = await X402Order.get_by_agent(agent_id, limit=limit)

        if not orders:
            return "No successful x402 payment orders found for this agent."

        result_parts = [f"Recent x402 Orders ({len(orders)}):"]

        for i, order in enumerate(orders, 1):
            # Format timestamp
            time_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

            # Format amount with decimals
            amount_str = format_amount(order.amount, order.asset)

            result_parts.append(f"\n[{i}] {time_str}")
            result_parts.append(f"    URL: {order.url}")
            if order.description:
                result_parts.append(f"    Description: {order.description}")
            result_parts.append(f"    Amount: {amount_str}")
            if order.tx_hash:
                result_parts.append(f"    TxHash: {order.tx_hash}")

        return "\n".join(result_parts)
