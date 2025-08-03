import logging
from typing import Optional, Type

import httpx
from eth_utils import is_address
from pydantic import BaseModel, Field

from .base import NationBaseTool

logger = logging.getLogger(__name__)


class NftCheckInput(BaseModel):
    nation_wallet_address: Optional[str] = Field(
        default=None, description="Nation wallet address"
    )


class NftCheck(NationBaseTool):
    name: str = "nft_check"
    description: str = "Check user nation pass NFTs stats in nation, including usage status and linked agents.By default, it will use the user_id as the wallet address. If you want to check other wallet address, please pass the nation_wallet_address parameter."
    args_schema: Type[BaseModel] = NftCheckInput

    async def _arun(self, nation_wallet_address: Optional[str] = None) -> str:
        """Implementation of the NFT Check tool.

        Args:
            nation_wallet_address: The wallet address of the nation (optional), if not passed, then get user_id from chat as wallet address.
            config: Configuration for the runnable.

        Returns:
            str: Formatted NFT check results based on the nation wallet address.
        """

        context = self.get_context()
        logger.debug(f"nft_check.py: Running NFT check with context {context}")

        # Use the provided nation_wallet_address or fetch it from the context
        if not nation_wallet_address:
            nation_wallet_address = context.user_id
            if not nation_wallet_address:
                raise ValueError(
                    "Nation wallet address is not provided and not found in context"
                )

        # Validate the normalized address
        if not is_address(nation_wallet_address):
            raise ValueError(
                f"Invalid Ethereum wallet address: {nation_wallet_address}"
            )

        url = f"{self.get_base_url()}/v1/users/{nation_wallet_address}"

        api_key = self.get_api_key()

        if not api_key:
            raise ValueError("Backend API key not found")

        headers = {"Accept": "application/json", "x-api-key": api_key}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    logger.error(
                        f"nft_check.py: Error from API: {response.status_code} - {response.text}"
                    )
                    return f"Error fetching NFT data: {response.status_code} - {response.text}"

                data = response.json()
                nfts = data.get("nfts", [])

                if not nfts:
                    return f"No NFTs found for wallet address: {nation_wallet_address}"

                # Format the NFT data
                formatted_results = (
                    f"NFTs for wallet address '{nation_wallet_address}':\n\n"
                )

                for i, nft in enumerate(nfts, 1):
                    token_id = nft.get("token_id", "Unknown")
                    used_by = nft.get("used_by", None)
                    linked_agent_id = nft.get("linked_agent_id", "None")

                    formatted_results += f"{i}. Token ID: {token_id}\n"
                    if used_by:
                        formatted_results += (
                            f"   Status: Used by Agent ID {linked_agent_id}\n"
                        )
                    else:
                        formatted_results += "   Status: Available\n"
                    formatted_results += "\n"

                return formatted_results.strip()

        except httpx.TimeoutException:
            logger.error("nft_check.py: Request timed out")
            return "The request to the NFT API timed out. Please try again later."
        except Exception as e:
            logger.error(f"nft_check.py: Error fetching NFT data: {e}", exc_info=True)
            return "An error occurred while fetching NFT data. Please try again later."
