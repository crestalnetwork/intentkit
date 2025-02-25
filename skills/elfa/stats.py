from typing import Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from .base import ElfaBaseTool, base_url


class ElfaGetSmartStatsInput(BaseModel):
    username: str = Field(description="username to get stats for")


class SmartStatsData(BaseModel):
    followerEngagementRatio: float | None = Field(
        description="the ratio of engagement by followers"
    )
    averageEngagement: float | None = Field(
        description="the average engagement of acount"
    )
    smartFollowingCount: float | None = Field(
        description="the count of smart followings"
    )


class ElfaGetSmartStatsOutput(BaseModel):
    success: bool
    data: SmartStatsData | None = Field(None, description="The stats data")


class ElfaGetSmartStats(ElfaBaseTool):
    """
    This tool uses the Elfa API to retrieve key social media metrics for a given username.  These metrics include:

    * **Smart Following Count:** A metric representing the number of high-quality or influential followers.
    * **Engagement Score:** A composite score reflecting the level of interaction with the user's content.
    * **Engagement Ratio:** The ratio of engagement (likes, comments, shares) to the number of followers.

    This tool is useful for:

    * **Competitor Analysis:** Compare your social media performance to that of your competitors.
    * **Influencer Identification:** Identify influential users in your niche.
    * **Social Media Audits:**  Assess the overall health and effectiveness of a social media presence.

    To use this tool, simply provide the desired username.  The tool will return the requested metrics.

    Attributes:
        name (str): Name of the tool, specifically "elfa_get_smart_stats".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "elfa_get_smart_stats"
    description: str = (
        """This tool uses the Elfa API to retrieve key social media metrics for a given username.  These metrics include:

        * **Smart Following Count:** A metric representing the number of high-quality or influential followers.
        * **Engagement Score:** A composite score reflecting the level of interaction with the user's content.
        * **Engagement Ratio:** The ratio of engagement (likes, comments, shares) to the number of followers.

        This tool is useful for:

        * **Competitor Analysis:** Compare your social media performance to that of your competitors.
        * **Influencer Identification:** Identify influential users in your niche.
        * **Social Media Audits:**  Assess the overall health and effectiveness of a social media presence.
        """
    )
    args_schema: Type[BaseModel] = ElfaGetSmartStatsInput

    def _run(self, username: str) -> ElfaGetSmartStatsOutput:
        """Run the tool retrieve smart stats (smart following count) and social metrics (engagement score and ratio) for a given username.

        Returns:
             ElfaGetMentionsOutput: A structured output containing output of Elfa get mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, username: str) -> ElfaGetSmartStatsOutput:
        """Run the tool retrieve smart stats (smart following count) and social metrics (engagement score and ratio) for a given username.

        Args:
            username (str): The username to check stats for.

        Returns:
            ElfaGetMentionsOutput: A structured output containing output of Elfa get mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        url = f"{base_url}/v1/account/smart-stats"
        headers = {
            "accept": "application/json",
            "x-elfa-api-key": self.api_key,
        }

        params = ElfaGetSmartStatsInput(username=username).model_dump(exclude_none=True)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=headers, timeout=30, params=params
                )
                response.raise_for_status()
                json_dict = response.json()

                res = ElfaGetSmartStatsOutput(**json_dict)

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
