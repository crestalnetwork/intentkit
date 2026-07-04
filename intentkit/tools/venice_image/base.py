from typing import Any

from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool
from intentkit.tools.venice_image.api import (
    make_venice_api_request,
)

venice_base_url = "https://api.venice.ai"


class VeniceImageBaseTool(IntentKitTool):
    """Base class for all Venice AI image-related tools."""

    category: str = "venice_image"

    def get_api_key(self) -> str:
        if not config.venice_api_key:
            raise ToolException("Venice API key is not configured")
        return config.venice_api_key

    async def post(
        self, path: str, payload: dict[str, Any], context
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """
        Makes a POST request to the Venice AI API using the `make_venice_api_request`
        function from the `tools.venice_image.api` module.

        This method handles the following:

        1.  Retrieving the API key using `get_api_key`.
        2.  Constructing the request payload.
        3.  Calling `make_venice_api_request` to make the actual API call.
        4.  Returning the results from `make_venice_api_request`.

        Args:
            path: The API endpoint path (e.g., "/api/v1/image/generate").
            payload: The request payload as a dictionary.
            context: The ToolContext for accessing API keys and configs.

        Returns:
            A tuple: (success_data, error_data).
            - If successful, success contains the JSON response from the API.
            - If an error occurs, success is an empty dictionary, and error contains error details.
        """
        api_key = self.get_api_key()

        return await make_venice_api_request(
            api_key, path, payload, self.category, self.name
        )
