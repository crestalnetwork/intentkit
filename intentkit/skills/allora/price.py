from decimal import Decimal
from typing import Literal

import httpx
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.allora.base import AlloraBaseTool

from .base import ALLORA_BASE_URL


class AlloraGetPriceInput(BaseModel):
    token: Literal["ETH", "BTC"] = Field(description="ETH or BTC")
    time_frame: Literal["5m", "8h"] = Field(description="5m or 8h")


class InferenceData(BaseModel):
    network_inference: str
    network_inference_normalized: str
    confidence_interval_percentiles: list[str]
    confidence_interval_percentiles_normalized: list[str]
    confidence_interval_values: list[str]
    confidence_interval_values_normalized: list[str]
    # topic_id: str
    # timestamp: int
    # extra_data: str


class Data(BaseModel):
    # signature: str
    token_decimals: int
    inference_data: InferenceData


class AlloraGetPriceOutput(BaseModel):
    # request_id: str
    # status: bool
    data: Data


class AlloraGetPrice(AlloraBaseTool):
    """Fetch ETH/BTC price predictions from Allora API."""

    name: str = "allora_get_price_prediction"
    description: str = (
        "Get ETH or BTC price prediction from Allora (5-minute or 8-hour)."
    )
    price: Decimal = Decimal("230")
    args_schema: ArgsSchema | None = AlloraGetPriceInput

    def _run(self, question: str) -> AlloraGetPriceOutput:
        """Run the tool to get the token price prediction from Allora API.

        Returns:
             AlloraGetPriceOutput: A structured output containing output of Allora toke price prediction API.

        Raises:
            Exception: If there's an error accessing the Allora API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(
        self, token: str, time_frame: str, **kwargs
    ) -> AlloraGetPriceOutput:
        """Run the tool to get the token price prediction from Allora API.
        Args:
            token (str): Token to get price prediction for.
            time_frame (str): Time frame for price prediction.
            config (RunnableConfig): The configuration for the runnable, containing agent context.

        Returns:
             AlloraGetPriceOutput: A structured output containing output of Allora toke price prediction API.

        Raises:
            Exception: If there's an error accessing the Allora API.
        """
        api_key = self.get_api_key()
        if not api_key:
            raise ToolException("Allora API key not found")

        url = f"{ALLORA_BASE_URL}/consumer/price/ethereum-11155111/{token}/{time_frame}"
        headers = {
            "accept": "application/json",
            "x-api-key": api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                json_dict = response.json()

                res = AlloraGetPriceOutput(**json_dict)

                return res
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"Request error from Allora API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"HTTP error from Allora API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"Error from Allora API: {e}") from e
