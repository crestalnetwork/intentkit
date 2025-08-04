import logging
from typing import Any, Dict, Type

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
        "Fetches the latest news articles from the CARV API. "
        "Returns a list of news items, each with a title, URL, and a short summary (card_text)."
    )
    args_schema: Type[BaseModel] = CarvNewsInput

    async def _arun(
        self,  # type: ignore
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Fetches news from the CARV API and returns the response.
        The expected successful response structure is a dictionary containing an "infos" key,
        which holds a list of news articles.
        Example: {"infos": [{"title": "...", "url": "...", "card_text": "..."}, ...]}
        """
        context = self.get_context()

        try:
            await self.apply_rate_limit(context)

            result, error = await self._call_carv_api(
                context=context,
                endpoint="/ai-agent-backend/news",
                method="GET",
            )

            if error is not None or result is None:
                logger.error(f"Error returned from CARV API (News): {error}")
                return {
                    "error": True,
                    "error_type": "APIError",
                    "message": "Failed to fetch news from CARV API.",
                    "details": error,  # error is the detailed error dict from _call_carv_api
                }

            # _call_carv_api returns response_json.get("data", response_json) on success.
            # For this endpoint, the "data" field should be {"infos": [...]}.
            # So, 'result' should be {"infos": [...]}.
            if "infos" not in result or not isinstance(result.get("infos"), list):
                logger.warning(
                    f"CARV API (News) response did not contain 'infos' list as expected: {result}"
                )
                return {
                    "error": True,
                    "error_type": "UnexpectedResponseFormat",
                    "message": "News data from CARV API is missing the 'infos' list or has incorrect format.",
                    "details": result,
                }

            # Successfully fetched and validated news data
            return result  # This will be {"infos": [...]}

        except Exception as e:
            logger.error(
                f"An unexpected error occurred while fetching news: {e}", exc_info=True
            )
            return {
                "error": True,
                "error_type": type(e).__name__,
                "message": "An unexpected error occurred while processing the news request.",
                "details": str(e),
            }
