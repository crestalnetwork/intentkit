from typing import Literal, Type

from pydantic import BaseModel, Field

from intentkit.clients.cdp import get_origin_cdp_client
from intentkit.skills.xmtp.base import XmtpBaseTool


class SwapPriceInput(BaseModel):
    """Input for querying swap price via CDP."""

    from_token: str = Field(description="The contract address to swap from")
    to_token: str = Field(description="The contract address to swap to")
    from_amount: str = Field(description="Input amount in smallest units (as string)")
    from_address: str = Field(
        description="The address where the from_token balance is located"
    )


class XmtpGetSwapPrice(XmtpBaseTool):
    """Skill for fetching indicative swap price using CDP SDK."""

    name: str = "xmtp_get_swap_price"
    description: str = "Get an indicative swap price/quote for token pair and amount on Base networks using CDP."
    response_format: Literal["content", "content_and_artifact"] = "content"
    args_schema: Type[BaseModel] = SwapPriceInput

    async def _arun(
        self,
        from_token: str,
        to_token: str,
        from_amount: str,
        from_address: str,
    ) -> str:
        context = self.get_context()
        agent = context.agent

        if agent.network_id not in ("base-mainnet", "base-sepolia"):
            raise ValueError(
                f"Swap price only supported on base-mainnet or base-sepolia. Current: {agent.network_id}"
            )

        network_for_cdp = {
            "base-mainnet": "base",
            "base-sepolia": "base-sepolia",
        }[agent.network_id]

        cdp_client = get_origin_cdp_client(self.skill_store)
        # Note: Don't use async with context manager as get_origin_cdp_client returns a managed global client
        price = await cdp_client.evm.get_swap_price(
            from_token=from_token,
            to_token=to_token,
            from_amount=str(from_amount),
            network=network_for_cdp,
            taker=from_address,
        )

        # Try to format a readable message from typical fields
        try:
            amount_out = getattr(price, "to_amount", None) or (
                price.get("to_amount") if isinstance(price, dict) else None
            )
            route = getattr(price, "route", None) or (
                price.get("route") if isinstance(price, dict) else None
            )
            route_str = f" via {route}" if route else ""
            if amount_out:
                return f"Estimated output: {amount_out} units of {to_token}{route_str} on {agent.network_id}."
        except Exception:
            pass

        return f"Swap price result (raw): {price}"
