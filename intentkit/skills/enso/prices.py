import httpx
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from .base import EnsoBaseTool, base_url


class EnsoGetPricesInput(BaseModel):
    chainId: int | None = Field(None, description="Chain ID")
    address: str = Field(
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        description="Token contract address",
    )


class EnsoGetPricesOutput(BaseModel):
    decimals: int | None = Field(None, ge=0, description="Token decimals")
    price: float | None = Field(None, gt=0, description="USD price")
    address: str | None = Field(None, description="Token address")
    symbol: str | None = Field(None, description="Token symbol")
    timestamp: int | None = Field(None, ge=0, description="Timestamp")
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
    description: str = "Get token USD price by chain ID and address."
    args_schema: ArgsSchema | None = EnsoGetPricesInput

    async def _arun(
        self,
        address: str,
        chainId: int | None = None,
        **kwargs,
    ) -> EnsoGetPricesOutput:
        """
        Asynchronous function to request the token price from the API.

        Args:
            chainId (int | None): The blockchain's chain ID. Defaults to the agent's configured network.
            address (str): Contract address of the token.

        Returns:
            EnsoGetPricesOutput: Token price response or error message.
        """
        context = self.get_context()
        resolved_chain_id = self.resolve_chain_id(context, chainId)
        api_token = self.get_api_token(context)

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/prices/{str(resolved_chain_id)}/{address}",
                    headers=headers,
                )
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
