from typing import Type

import httpx
from pydantic import BaseModel, Field

from .base import EnsoBaseTool, base_url, default_chain_id


class EnsoGetPricesInput(BaseModel):
    chainId: int = Field(
        default_chain_id, description="Blockchain chain ID of the token"
    )
    address: str = Field(
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        description="Contract address of the token",
    )


class PriceInfo(BaseModel):
    decimals: int | None = Field(None, ge=0, description="Number of decimals")
    price: float | None = Field(None, gt=0, description="Price in the smallest unit")
    address: str | None = Field(None, description="Contract address")
    symbol: str | None = Field(None, description="Token symbol")
    timestamp: int | None = Field(None, ge=0, description="Timestamp in seconds")
    chainId: int | None = Field(None, ge=0, description="Chain ID")


class EnsoGetPricesOutput(BaseModel):
    res: PriceInfo | None = Field(
        None, description="Price information of the requested token"
    )
    error: str | None = Field(
        None, description="Error message if price retrieval fails"
    )


class EnsoGetPrices(EnsoBaseTool):
    """
    Tool allows fetching the price in USD for a given blockchain's token.

    Attributes:
        name (str): Name of the tool, specifically "enso_get_tokens".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_get_prices"
    description: str = "Retrieve the price of a token by chain ID and contract address"
    args_schema: Type[BaseModel] = EnsoGetPricesInput

    def _run(
        self,
        chainId: int = default_chain_id,
        address: str = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    ) -> EnsoGetPricesOutput:
        """
        Asynchronous function to request the token price from the API.

        Args:
            chainId (int): The blockchain's chain ID.
            address (str): Contract address of the token.

        Returns:
            EnsoGetPricesOutput: Token price response or error message.
        """
        url = f"{base_url}/api/v1/prices/{str(chainId)}/{address}"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

        with httpx.Client() as client:
            try:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                json_dict = response.json()

                # Parse the response into a `PriceInfo` object
                price_info = PriceInfo(**json_dict)

                # Return the parsed response
                return EnsoGetPricesOutput(res=price_info, error=None)
            except httpx.RequestError as req_err:
                return EnsoGetPricesOutput(res=None, error=f"Request error: {req_err}")
            except httpx.HTTPStatusError as http_err:
                return EnsoGetPricesOutput(res=None, error=f"HTTP error: {http_err}")
            except Exception as e:
                return EnsoGetPricesOutput(res=None, error=str(e))

    async def _arun(
        self,
        chainId: int = default_chain_id,
        address: str = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    ) -> EnsoGetPricesOutput:
        """Async implementation of the tool.

        This tool doesn't have a native async implementation, so we call the sync version.
        """
        return self._run(chainId, address)
