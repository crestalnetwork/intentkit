from typing import Type

import httpx
from langchain.tools.base import ToolException
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


class EnsoGetPricesOutput(BaseModel):
    decimals: int | None = Field(None, ge=0, description="Number of decimals")
    price: float | None = Field(None, gt=0, description="Price in the smallest unit")
    address: str | None = Field(None, description="Contract address")
    symbol: str | None = Field(None, description="Token symbol")
    timestamp: int | None = Field(None, ge=0, description="Timestamp in seconds")
    chainId: int | None = Field(None, ge=0, description="Chain ID")


class EnsoGetPrices(EnsoBaseTool):
    """
    Tool allows fetching the price in USD for a given blockchain's token.

    Attributes:
        name (str): Name of the tool, specifically "enso_get_prices".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_get_prices"
    description: str = "Retrieve the price of a token by chain ID and contract address"
    args_schema: Type[BaseModel] = EnsoGetPricesInput

    async def _arun(
        self,
        address: str,
        chainId: int = default_chain_id,
        **kwargs,
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

        context = self.get_context()
        api_token = self.get_api_token(context)

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                json_dict = response.json()

                # Parse the response into a `PriceInfo` object
                res = EnsoGetPricesOutput(**json_dict)

                # Return the parsed response
                return res
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Enso API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Enso API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"error from Enso API: {e}") from e
