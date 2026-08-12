"""Shared HTTP client behavior for Xquik tools."""

from typing import Any

import httpx
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool

XQUIK_BASE_URL = "https://xquik.com/api/v1"


class XquikBaseTool(IntentKitTool):
    """Base class for authenticated Xquik reads."""

    category: str = "xquik"

    def get_api_key(self) -> str:
        """Return the configured Xquik API key."""
        if not config.xquik_api_key:
            raise ToolException("Xquik API key is not configured")
        return config.xquik_api_key

    async def get(
        self,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Call one authenticated Xquik GET endpoint."""
        headers = {
            "accept": "application/json",
            "x-api-key": self.get_api_key(),
        }
        clean_params = {
            key: value for key, value in params.items() if value is not None
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{XQUIK_BASE_URL}{path}",
                    headers=headers,
                    params=clean_params,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ToolException(
                f"Xquik API returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ToolException("Xquik API request failed") from exc
        except ValueError as exc:
            raise ToolException("Xquik API returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise ToolException("Xquik API returned an unexpected response")
        return payload
