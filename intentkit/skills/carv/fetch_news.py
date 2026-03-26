import logging
from typing import Any

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel

from intentkit.skills.carv.base import CarvBaseTool

logger = logging.getLogger(__name__)


class CarvNewsInput(BaseModel):
    """
    Input schema for CARV News API.
    This API endpoint does not require any specific parameters from the user.
    """

    pass


class FetchNewsTool(CarvBaseTool):
    """
    Tool for fetching the latest news articles from the CARV API.
    This tool retrieves a list of recent news items, each including a title, URL, and a short description (card_text).
    It's useful for getting up-to-date information on various topics covered by CARV's news aggregation.
    """

    name: str = "carv_fetch_news"
    description: str = (
        "Fetch latest news articles from CARV API with title, URL, and summary."
    )
    args_schema: ArgsSchema | None = CarvNewsInput

    async def _arun(
        self,  # type: ignore
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Fetches news from the CARV API and returns the response.
        The expected successful response structure is a dictionary containing an "infos" key,
        which holds a list of news articles.
        Example: {"infos": [{"title": "...", "url": "...", "card_text": "..."}, ...]}
        """
        context = self.get_context()

        await self.apply_rate_limit(context)

        result = await self._call_carv_api(
            context=context,
            endpoint="/ai-agent-backend/news",
            method="GET",
        )

        if "infos" not in result or not isinstance(result.get("infos"), list):
            logger.warning(
                "CARV API (News) response did not contain 'infos' list as expected: %s",
                result,
            )
            raise ToolException(
                "News data from CARV API is missing the 'infos' list or has incorrect format."
            )

        return result
