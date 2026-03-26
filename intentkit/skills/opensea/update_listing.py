"""OpenSea update listing skill — change listing price (cancel + relist)."""

import json
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.opensea.constants import OPENSEA_PROTOCOL_ADDRESS
from intentkit.skills.opensea.onchain_base import OpenSeaOnChainBaseTool

NAME = "opensea_update_listing"


class UpdateListingInput(BaseModel):
    """Input for updating an OpenSea listing price."""

    order_hash: str = Field(description="The order hash of the listing to update")
    chain: str = Field(
        description=(
            "The blockchain name (e.g., 'ethereum', 'matic', 'base', 'arbitrum')"
        )
    )
    protocol_address: str = Field(
        description="The protocol contract address (from get_listings)"
    )
    contract_address: str = Field(description="The ERC721 NFT contract address")
    token_id: str = Field(description="The token ID of the listed NFT")
    new_price: str = Field(
        description="New listing price in ETH (e.g., '0.5' for 0.5 ETH)"
    )
    expiration_hours: int = Field(
        default=168,
        description="New listing duration in hours (default 168 = 7 days)",
        ge=1,
        le=8760,
    )


class OpenSeaUpdateListing(OpenSeaOnChainBaseTool):
    """Update the price of an existing NFT listing on OpenSea."""

    name: str = NAME
    description: str = (
        "Update the price of an existing NFT listing on OpenSea. "
        "This cancels the old listing and creates a new one with the new price. "
        "Requires the old order details and the new price. "
        "Requires an on-chain wallet."
    )
    args_schema: ArgsSchema | None = UpdateListingInput

    @override
    async def _arun(
        self,
        order_hash: str,
        chain: str,
        protocol_address: str,
        contract_address: str,
        token_id: str,
        new_price: str,
        expiration_hours: int = 168,
        **kwargs: Any,
    ) -> str:
        try:
            if not self.is_onchain_capable():
                raise ToolException(
                    "This agent does not have an on-chain wallet configured"
                )

            _, cancel_error = await self._post(
                f"/orders/chain/{chain}/protocol/{protocol_address}/{order_hash}/cancel",
            )
            if cancel_error:
                return json.dumps(
                    {
                        "error": "Failed to cancel old listing",
                        "details": cancel_error,
                    }
                )

            wallet_address = await self.get_wallet_address()
            new_price_wei = Web3.to_wei(Decimal(new_price), "ether")
            counter = await self._get_seaport_counter(wallet_address)

            order_params = self._build_listing_order(
                offerer=wallet_address,
                contract_address=contract_address,
                token_id=token_id,
                price_wei=new_price_wei,
                expiration_hours=expiration_hours,
                counter=counter,
            )

            signature = await self._sign_seaport_order(order_params)

            data, error = await self._post(
                f"/orders/{chain}/seaport/listings",
                json_data={
                    "parameters": order_params,
                    "signature": signature,
                    "protocol_address": OPENSEA_PROTOCOL_ADDRESS,
                },
            )

            if error:
                return json.dumps(error)

            result = "**Listing Updated on OpenSea**\n"
            result += f"Old Order: {order_hash} (cancelled)\n"
            result += f"Contract: {contract_address}\n"
            result += f"Token ID: {token_id}\n"
            result += f"New Price: {new_price} ETH\n"
            result += f"Chain: {chain}\n"
            if isinstance(data, dict):
                new_order_hash = data.get("order_hash", "unknown")
                result += f"New Order Hash: {new_order_hash}\n"

            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to update listing: {e!s}")
