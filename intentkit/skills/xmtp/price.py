from typing import Literal, override

from cdp.actions.evm.swap.types import SwapPriceResult
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.xmtp.base import XmtpBaseTool
from intentkit.wallets.cdp import get_cdp_client


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
    description: str = "Get an indicative swap price/quote for token pair and amount on Ethereum, Base, Arbitrum, and Optimism mainnet networks using CDP."
    response_format: Literal["content", "content_and_artifact"] = "content"
    args_schema: ArgsSchema | None = SwapPriceInput

    @override
    async def _arun(
        self,
        from_token: str,
        to_token: str,
        from_amount: str,
        from_address: str,
    ) -> str:
        context = self.get_context()
        agent = context.agent

        # Only support mainnet networks for price and swap
        supported_networks = [
            "ethereum-mainnet",
            "base-mainnet",
            "arbitrum-mainnet",
            "optimism-mainnet",
        ]
        if agent.network_id not in supported_networks:
            raise ToolException(
                f"Swap price only supported on {', '.join(supported_networks)}. Current: {agent.network_id}"
            )

        network_for_cdp = self._resolve_cdp_network_name(agent.network_id)

        cdp_client = get_cdp_client()
        # Note: Don't use async with context manager as get_cdp_client returns a managed global client
        price: SwapPriceResult = await cdp_client.evm.get_swap_price(
            from_token=from_token,
            to_token=to_token,
            from_amount=str(from_amount),
            network=network_for_cdp,
            taker=from_address,
        )

        # Try to format a readable message from typical fields
        if price.to_amount:
            return f"Estimated output: {price.to_amount} units of {price.to_token} on {agent.network_id}."

        return f"Swap price result (raw): {price}"
