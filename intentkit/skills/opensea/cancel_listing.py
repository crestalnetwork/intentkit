"""OpenSea cancel listing skill — cancel an existing listing off-chain."""

import json
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_cancel_listing"


class CancelListingInput(BaseModel):
    """Input for canceling an OpenSea listing."""

    order_hash: str = Field(description="The order hash of the listing to cancel")
    protocol_address: str = Field(
        description="The protocol contract address (from get_listings)"
    )
    chain: str = Field(
        description=(
            "The blockchain name (e.g., 'ethereum', 'matic', 'base', 'arbitrum')"
        )
    )


class OpenSeaCancelListing(OpenSeaBaseTool):
    """Cancel an existing NFT listing on OpenSea."""

    name: str = NAME
    description: str = (
        "Cancel an existing NFT listing on OpenSea. "
        "This is an off-chain cancellation — no gas required. "
        "Requires the order_hash, protocol_address, and chain from get_listings. "
        "Note: cancellation may not be effective if a fulfillment "
        "signature was already issued."
    )
    args_schema: ArgsSchema | None = CancelListingInput

    @override
    async def _arun(
        self,
        order_hash: str,
        protocol_address: str,
        chain: str,
        **kwargs: Any,
    ) -> str:
        try:
            _, error = await self._post(
                f"/orders/chain/{chain}/protocol/{protocol_address}/{order_hash}/cancel",
            )

            if error:
                return json.dumps(error)

            return (
                f"**Listing Cancelled on OpenSea**\n"
                f"Order Hash: {order_hash}\n"
                f"Chain: {chain}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to cancel listing: {e!s}")
