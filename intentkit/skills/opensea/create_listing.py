"""OpenSea create listing skill — list an NFT for sale."""

import json
from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field
from web3 import Web3

from intentkit.skills.opensea.constants import OPENSEA_PROTOCOL_ADDRESS
from intentkit.skills.opensea.onchain_base import OpenSeaOnChainBaseTool

NAME = "opensea_create_listing"


class CreateListingInput(BaseModel):
    """Input for creating an NFT listing on OpenSea."""

    contract_address: str = Field(description="The ERC721 NFT contract address")
    token_id: str = Field(description="The token ID of the NFT to list")
    price: str = Field(description="Listing price in ETH (e.g., '0.5' for 0.5 ETH)")
    expiration_hours: int = Field(
        default=168,
        description="Listing duration in hours (default 168 = 7 days)",
        ge=1,
        le=8760,
    )


class OpenSeaCreateListing(OpenSeaOnChainBaseTool):
    """Create a listing to sell an NFT on OpenSea."""

    name: str = NAME
    description: str = (
        "Create a listing to sell an NFT on OpenSea marketplace. "
        "Requires the NFT contract address, token ID, and price in ETH. "
        "The NFT will be approved for OpenSea if not already. "
        "Requires an on-chain wallet."
    )
    args_schema: ArgsSchema | None = CreateListingInput

    @override
    async def _arun(
        self,
        contract_address: str,
        token_id: str,
        price: str,
        expiration_hours: int = 168,
        **kwargs: Any,
    ) -> str:
        try:
            if not self.is_onchain_capable():
                raise ToolException(
                    "This agent does not have an on-chain wallet configured"
                )

            chain = self._get_chain_name()
            wallet_address = await self.get_wallet_address()
            price_wei = Web3.to_wei(Decimal(price), "ether")

            approval_tx = await self._ensure_nft_approval(
                contract_address, wallet_address
            )
            counter = await self._get_seaport_counter(wallet_address)

            order_params = self._build_listing_order(
                offerer=wallet_address,
                contract_address=contract_address,
                token_id=token_id,
                price_wei=price_wei,
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

            result = "**NFT Listed on OpenSea**\n"
            result += f"Contract: {contract_address}\n"
            result += f"Token ID: {token_id}\n"
            result += f"Price: {price} ETH\n"
            result += f"Chain: {chain}\n"
            if approval_tx:
                result += f"Approval Tx: {approval_tx}\n"
            if isinstance(data, dict):
                order_hash = data.get("order_hash", "unknown")
                result += f"Order Hash: {order_hash}\n"

            return result

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to create listing: {e!s}")
