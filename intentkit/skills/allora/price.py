from typing import Literal, Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.allora.base import AlloraBaseTool

from .base import base_url


class AlloraGetPriceInput(BaseModel):
    token: Literal["ETH", "BTC"] = Field(
        description="Token to get price prediction for"
    )
    time_frame: Literal["5m", "8h"] = Field(
        description="Time frame for price prediction, it can be 5 minutes or 8 hours"
    )


class InferenceData(BaseModel):
    network_inference: str = Field(description="Network Inference")
    network_inference_normalized: str = Field(
        description="Model's prediction or estimate, scaled or adjusted to a standard range or unit."
    )
    confidence_interval_percentiles: list[str] = Field(
        description="Represent a range of values within which the model predicts the actual price is likely to fall, with a certain level of confidence."
    )
    confidence_interval_percentiles_normalized: list[str] = Field(
        description="a range of values within which the model predicts the actual price is likely to fall), but the values defining the interval have been normalized."
    )
    confidence_interval_values: list[str] = Field(
        description=" is a list (or array) of values that define the boundaries of a confidence interval in a prediction.  These values correspond to specific percentiles and represent the range within which the model predicts the true value (e.g., future price) is likely to fall."
    )
    confidence_interval_values_normalized: list[str] = Field(
        description="is a list (or array) of values that define the boundaries of a confidence interval, just like confidence_interval_values, but these values have been normalized.  Normalization means the values have been scaled or transformed to a standard range, typically between 0 and 1 (or sometimes -1 and 1)."
    )
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
    """
    The Allora Price Prediction Feed tool fetches the price prediction feed from the Allora API.
    Ethereum (ETH) or Bitcoin (BTC) price predictions (5-minute, 8-hour)


    Attributes:
        name (str): Name of the tool, specifically "get_price_prediction".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "allora_get_price_prediction"
    description: str = """
        The Allora Price Prediction Feed tool fetches the price prediction feed from the Allora API.
        Ethereum (ETH) or Bitcoin (BTC) price predictions (5-minute, 8-hour)
        """
    args_schema: Type[BaseModel] = AlloraGetPriceInput

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
            raise ValueError("Allora API key not found")

        url = f"{base_url}/consumer/price/ethereum-11155111/{token}/{time_frame}"
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
