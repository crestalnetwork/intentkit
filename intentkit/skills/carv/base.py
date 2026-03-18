import logging
from typing import Any

import httpx
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)

CARV_API_BASE_URL = "https://interface.carv.io"


class CarvBaseTool(IntentKitSkill):
    """Base class for CARV API tools."""

    category: str = "carv"

    def get_api_key(self) -> str:
        if not config.carv_api_key:
            raise ToolException("CARV API key is not configured")
        return config.carv_api_key

    async def apply_rate_limit(self, context) -> None:
        """Apply rate limiting if configured in the agent's skill_config."""
        skill_config = context.agent.skill_config(self.category)
        limit_num = skill_config.get("rate_limit_number")
        limit_min = skill_config.get("rate_limit_minutes")
        if limit_num and limit_min:
            await self.user_rate_limit_by_category(limit_num, limit_min * 60)

    async def _call_carv_api(
        self,
        context,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """
        Makes a call to the CARV API and returns a tuple of (success, error).

        Args:
            context: The skill context.
            endpoint: The API endpoint path (e.g., "/ai-agent-backend/token_info").
            method: HTTP method ("GET", "POST", etc.).
            params: Query parameters for the request.
            payload: JSON payload for POST/PUT requests.

        Returns:
            Tuple where the first element is the response data if successful,
            and the second element is an error dict if an error occurred.
        """

        url = f"{CARV_API_BASE_URL}{endpoint}"

        try:
            api_key = self.get_api_key()

            headers = {
                "Authorization": api_key,
                "Content-Type": "application/json",
            }

            logger.debug(
                f"Calling CARV API: {method} {url} with params {params}, payload {payload}"
            )

            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(
                        url, headers=headers, json=payload, params=params
                    )
                else:
                    return None, {"error": f"Unsupported HTTP method: {method}"}

                # Do NOT raise for status here; always parse JSON
                try:
                    response_json: dict[str, Any] = response.json()
                except Exception as json_err:
                    err_msg = f"Failed to parse JSON response: {json_err}"
                    logger.error(err_msg)
                    return None, {"error": err_msg}

                logger.debug(
                    f"CARV API Response (status {response.status_code}): {response_json}"
                )

                # Check if response_json signals an error explicitly (custom API error)
                if response.status_code >= 400 or "error" in response_json:
                    # Return full error info (including status code, body, etc.)
                    return None, {
                        "error": response_json.get("error", "Unknown API error"),
                        "status_code": response.status_code,
                        "response": response_json,
                        "url": url,
                        "method": method,
                        "params": params,
                        "payload": payload,
                    }

                # Otherwise return the 'data' field if present, else full response
                return response_json.get("data", response_json), None

        except Exception as e:
            logger.error(
                f"Error calling CARV API to {method} > {url}: {e}", exc_info=True
            )
            return None, {
                "error": str(e),
                "url": url,
                "method": method,
                "params": params,
            }
