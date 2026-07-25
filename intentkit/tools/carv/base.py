import logging
from typing import Any

import httpx
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool

logger = logging.getLogger(__name__)

CARV_API_BASE_URL = "https://interface.carv.io"


class CarvBaseTool(IntentKitTool):
    """Base class for CARV API tools."""

    category: str = "carv"

    def get_api_key(self) -> str:
        if not config.carv_api_key:
            raise ToolException("CARV API key is not configured")
        return config.carv_api_key

    async def _call_carv_api(
        self,
        context,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Makes a call to the CARV API and returns the response data.

        Args:
            context: The tool context.
            endpoint: The API endpoint path (e.g., "/ai-agent-backend/token_info").
            method: HTTP method ("GET", "POST", etc.).
            params: Query parameters for the request.
            payload: JSON payload for POST/PUT requests.

        Returns:
            The response data dict on success.

        Raises:
            ToolException: On API errors, network errors, or invalid responses.
        """
        url = f"{CARV_API_BASE_URL}{endpoint}"

        try:
            api_key = self.get_api_key()

            headers = {
                "Authorization": api_key,
                "Content-Type": "application/json",
            }

            logger.debug(
                "Calling CARV API: %s %s with params %s, payload %s",
                method,
                url,
                params,
                payload,
            )

            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(
                        url, headers=headers, json=payload, params=params
                    )
                else:
                    raise ToolException(f"Unsupported HTTP method: {method}")

                try:
                    response_json: dict[str, Any] = response.json()
                except Exception as json_err:
                    raise ToolException(f"Failed to parse JSON response: {json_err!s}")

                logger.debug(
                    "CARV API Response (status %d): %s",
                    response.status_code,
                    response_json,
                )

                if response.status_code >= 400 or "error" in response_json:
                    error_msg = response_json.get("error", "Unknown API error")
                    raise ToolException(
                        f"CARV API error ({response.status_code}): {error_msg}"
                    )

                return response_json.get("data", response_json)

        except ToolException:
            raise
        except Exception as e:
            logger.exception("Error calling CARV API to %s > %s: %s", method, url, e)
            raise ToolException(f"CARV API request failed: {e!s}")
