from typing import Type

import httpx
from langchain.tools.base import ToolException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .base import ElfaBaseTool, base_url


class ElfaGetTrendingTokensInput(BaseModel):
    timeWindow: str | None = Field(
        "24h", description="Time window for trending analysis"
    )
    minMentions: int | None = Field(
        5, description="Minimum number of mentions required"
    )


class Trends(BaseModel):
    change_percent: int | None = Field(description="change percentage of token trend")
    previous_count: int | None = Field(description="previous count")
    current_count: int | None = Field(description="current count")
    token: str | None = Field(description="token")


class TrendsData(BaseModel):
    data: list[Trends] | None = Field(None, description="trending tokens")


class ElfaGetTrendingTokensOutput(BaseModel):
    success: bool
    data: TrendsData | None = Field(None, description="The result")


class ElfaGetTrendingTokens(ElfaBaseTool):
    """
    This tool ranks the most discussed tokens based on smart mentions count for a given period, with updates every 5 minutes via the Elfa API.  Smart mentions provide a more sophisticated measure of discussion volume than simple keyword counts.

    **Use Cases:**

    * Identify trending tokens: Quickly see which tokens are gaining traction in online discussions.
    * Gauge market sentiment:  Track changes in smart mention counts to understand shifts in market opinion.
    * Research potential investments: Use the ranking as a starting point for further due diligence.

    **Example Usage:**

    To use this tool, you would typically specify a time window (e.g., the last hour, the last 24 hours). The tool will then return a ranked list of tokens, along with their corresponding smart mention counts.

    Attributes:
        name (str): Name of the tool, specifically "elfa_get_trending_tokens".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "elfa_get_trending_tokens"
    description: str = """This tool ranks the most discussed tokens based on smart mentions count for a given period, with updates every 5 minutes via the Elfa API.  Smart mentions provide a more sophisticated measure of discussion volume than simple keyword counts.

        **Use Cases:**

        * Identify trending tokens: Quickly see which tokens are gaining traction in online discussions.
        * Gauge market sentiment:  Track changes in smart mention counts to understand shifts in market opinion.
        * Research potential investments: Use the ranking as a starting point for further due diligence.

        **Example Usage:**

        To use this tool, you would typically specify a time window (e.g., the last hour, the last 24 hours). The tool will then return a ranked list of tokens, along with their corresponding smart mention counts."""
    args_schema: Type[BaseModel] = ElfaGetTrendingTokensInput

    async def _arun(
        self,
        timeWindow: str = "24h",
        minMentions: int = 5,
        config: RunnableConfig = None,
        **kwargs,
    ) -> ElfaGetTrendingTokensOutput:
        """Run the tool to ranks the most discussed tokens by smart mentions count for a given period, updated every 5 minutes via the Elfa API.

        Args:
            timeWindow: Time window for trending tokens (e.g., '1h', '24h', '7d').
            minMentions: Minimum number of mentions for a token.
            config: The configuration for the runnable, containing agent context.
            **kwargs: Additional parameters.

        Returns:
            ElfaGetMentionsOutput: A structured output containing output of Elfa get mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        context = self.context_from_config(config)
        api_key = self.get_api_key(context)
        if not api_key:
            raise ValueError("Elfa API key not found")

        url = f"{base_url}/v1/trending-tokens"
        headers = {
            "accept": "application/json",
            "x-elfa-api-key": api_key,
        }

        params = ElfaGetTrendingTokensInput(
            timeWindow=timeWindow, page=1, pageSize=50, minMentions=minMentions
        ).model_dump(exclude_none=True)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=headers, timeout=30, params=params
                )
                response.raise_for_status()
                json_dict = response.json()

                res = ElfaGetTrendingTokensOutput(**json_dict)

                return res
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Elfa API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Elfa API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"error from Elfa API: {e}") from e
