"""OpenSea base classes with shared HTTP client mixin."""

import json
import logging
from typing import Any

import httpx
from langchain_core.tools.base import ToolException

from intentkit.config.config import config as system_config
from intentkit.skills.base import IntentKitSkill
from intentkit.skills.opensea.constants import OPENSEA_API_BASE_URL

logger = logging.getLogger(__name__)

ApiResult = tuple[dict[str, Any] | None, dict[str, Any] | None]


class OpenSeaApiMixin:
    """Mixin providing OpenSea API HTTP client methods.

    Shared by both read-only and on-chain OpenSea skill base classes.
    """

    base_url: str = OPENSEA_API_BASE_URL

    def _get_api_key(self) -> str:
        api_key = system_config.opensea_api_key
        if not api_key:
            raise ToolException("OpenSea API key is not configured")
        return api_key

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self._get_api_key(),
            "Accept": "application/json",
        }

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> ApiResult:
        """Make an async GET request to the OpenSea API.

        Returns:
            A tuple (data, error_details):
            - (dict, None) on success
            - (None, dict) on error
        """
        if not path.startswith("/"):
            path = "/" + path

        url = f"{self.base_url}{path}"
        logger.debug("OpenSea API GET %s params=%s", url, params)

        response = None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=self._headers())

                try:
                    response_data = response.json()
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse OpenSea response from %s", url)
                    return None, {
                        "error": "Failed to parse OpenSea API response",
                        "error_type": "parsing_error",
                        "status_code": response.status_code,
                        "details": str(e),
                    }

                if response.is_success:
                    return response_data, None
                else:
                    logger.warning(
                        "OpenSea API error: %s - %s",
                        response.status_code,
                        response.text,
                    )
                    return None, {
                        "error": "OpenSea API request failed",
                        "error_type": "api_error",
                        "status_code": response.status_code,
                        "response_body": response_data,
                    }

        except httpx.RequestError as e:
            logger.error("Connection error to OpenSea API: %s", e)
            return None, {
                "error": "Failed to connect to OpenSea API",
                "error_type": "connection_error",
                "details": str(e),
            }
        except Exception as e:
            logger.exception("Unexpected error during OpenSea API call: %s", e)
            return None, {
                "error": "Unexpected error during OpenSea API call",
                "error_type": "unexpected_error",
                "status_code": response.status_code if response else None,
                "details": str(e),
            }

    async def _post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> ApiResult:
        """Make an async POST request to the OpenSea API.

        Returns:
            A tuple (data, error_details):
            - (dict, None) on success
            - (None, dict) on error
        """
        if not path.startswith("/"):
            path = "/" + path

        url = f"{self.base_url}{path}"
        logger.debug("OpenSea API POST %s", url)

        response = None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=json_data, headers=self._headers()
                )

                try:
                    response_data = response.json()
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse OpenSea response from %s", url)
                    return None, {
                        "error": "Failed to parse OpenSea API response",
                        "error_type": "parsing_error",
                        "status_code": response.status_code,
                        "details": str(e),
                    }

                if response.is_success:
                    return response_data, None
                else:
                    logger.warning(
                        "OpenSea API error: %s - %s",
                        response.status_code,
                        response.text,
                    )
                    return None, {
                        "error": "OpenSea API request failed",
                        "error_type": "api_error",
                        "status_code": response.status_code,
                        "response_body": response_data,
                    }

        except httpx.RequestError as e:
            logger.error("Connection error to OpenSea API: %s", e)
            return None, {
                "error": "Failed to connect to OpenSea API",
                "error_type": "connection_error",
                "details": str(e),
            }
        except Exception as e:
            logger.exception("Unexpected error during OpenSea API call: %s", e)
            return None, {
                "error": "Unexpected error during OpenSea API call",
                "error_type": "unexpected_error",
                "status_code": response.status_code if response else None,
                "details": str(e),
            }


class OpenSeaBaseTool(OpenSeaApiMixin, IntentKitSkill):
    """Base class for read-only OpenSea API skills."""

    category: str = "opensea"
