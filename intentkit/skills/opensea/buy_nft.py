"""OpenSea buy NFT skill — fulfill a listing to purchase an NFT."""

import json
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.opensea.onchain_base import OpenSeaOnChainBaseTool

NAME = "opensea_buy_nft"


class BuyNftInput(BaseModel):
    """Input for buying an NFT on OpenSea."""

    order_hash: str = Field(
        description="The order hash of the listing to fulfill (from get_listings)"
    )
    protocol_address: str = Field(
        description="The protocol contract address (from get_listings)"
    )


class OpenSeaBuyNft(OpenSeaOnChainBaseTool):
    """Buy an NFT by fulfilling a listing on OpenSea."""

    name: str = NAME
    description: str = (
        "Buy an NFT by fulfilling a listing on OpenSea. "
        "Requires the order_hash and protocol_address from get_listings. "
        "The purchase price (in ETH) will be sent as part of the transaction. "
        "Requires an on-chain wallet with sufficient ETH balance."
    )
    args_schema: ArgsSchema | None = BuyNftInput

    @override
    async def _arun(
        self,
        order_hash: str,
        protocol_address: str,
        **kwargs: Any,
    ) -> str:
        try:
            if not self.is_onchain_capable():
                raise ToolException(
                    "This agent does not have an on-chain wallet configured"
                )

            chain = self._get_chain_name()
            wallet = await self.get_unified_wallet()
            wallet_address = wallet.address

            data, error = await self._post(
                "/listings/fulfillment_data",
                json_data={
                    "listing": {
                        "hash": order_hash,
                        "chain": chain,
                        "protocol_address": protocol_address,
                    },
                    "fulfiller": {"address": wallet_address},
                },
            )

            if error:
                return json.dumps(error)

            if not data or "fulfillment_data" not in data:
                raise ToolException("Failed to get fulfillment data from OpenSea")

            fulfillment = data["fulfillment_data"]
            transaction = fulfillment.get("transaction", {})

            to_address = transaction.get("to")
            input_data = transaction.get("input_data", {})
            tx_data = input_data.get("data") if isinstance(input_data, dict) else None
            raw_value = transaction.get("value", 0)
            if isinstance(raw_value, str) and raw_value.startswith("0x"):
                value = int(raw_value, 16)
            else:
                value = int(raw_value)

            if not to_address or not tx_data:
                raise ToolException(
                    "Incomplete transaction data from OpenSea fulfillment"
                )

            tx_hash = await wallet.send_transaction(
                to=to_address,
                data=tx_data,
                value=value,
            )

            receipt = await wallet.wait_for_receipt(tx_hash)
            if receipt.get("status", 0) != 1:
                raise ToolException(f"Purchase transaction failed. Hash: {tx_hash}")

            return (
                f"**NFT Purchased on OpenSea**\n"
                f"Order Hash: {order_hash}\n"
                f"Tx: {tx_hash}\n"
                f"Chain: {chain}"
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to buy NFT: {e!s}")
