from typing import Any, Dict, List, Type

import httpx
from pydantic import BaseModel

from intentkit.skills.cookiefun.base import CookieFunBaseTool, logger
from intentkit.skills.cookiefun.constants import DEFAULT_HEADERS, ENDPOINTS


class GetSectorsInput(BaseModel):
    """Input for GetSectors tool."""

    pass


class GetSectors(CookieFunBaseTool):
    """Tool to get all available sectors from the CookieFun API."""

    name: str = "cookiefun_get_sectors"
    description: str = (
        "Returns a list of all available sectors in the CookieFun system."
    )
    args_schema: Type[BaseModel] = GetSectorsInput

    async def _arun(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Get all available sectors from the CookieFun API.

        Returns:
            List of sector objects, each containing id, name, and other metadata.
        """
        logger.info("Getting sectors from CookieFun API")
        try:
            # Get API key
            api_key = self.get_api_key()

            if not api_key:
                logger.error("No API key provided for CookieFun API")
                return "Error: No API key provided for CookieFun API. Please configure the API key in the agent settings."

            # Make API request
            headers = {**DEFAULT_HEADERS, "x-api-key": api_key}

            async with httpx.AsyncClient() as client:
                response = await client.get(ENDPOINTS["sectors"], headers=headers)
                logger.debug(
                    "Received response with status code: %d", response.status_code
                )

                response.raise_for_status()
                data = response.json()

                # Check different possible response structures
                if data.get("success") and "ok" in data and "entries" in data["ok"]:
                    sectors = data["ok"]["entries"]
                    logger.info(
                        "Successfully retrieved %d sectors from entries field",
                        len(sectors),
                    )
                    return sectors
                elif data.get("success") and "ok" in data and "sectors" in data["ok"]:
                    sectors = data["ok"]["sectors"]
                    logger.info("Successfully retrieved %d sectors", len(sectors))
                    return sectors
                elif (
                    data.get("success")
                    and "ok" in data
                    and isinstance(data["ok"], list)
                ):
                    # If "ok" is directly a list
                    sectors = data["ok"]
                    logger.info(
                        "Successfully retrieved %d sectors from ok list", len(sectors)
                    )
                    return sectors
                elif data.get("success") and isinstance(data.get("sectors"), list):
                    # If sectors is at the top level
                    sectors = data["sectors"]
                    logger.info(
                        "Successfully retrieved %d sectors from top level", len(sectors)
                    )
                    return sectors
                elif data.get("success") and isinstance(data.get("entries"), list):
                    # If entries is at the top level
                    sectors = data["entries"]
                    logger.info(
                        "Successfully retrieved %d sectors from entries top level",
                        len(sectors),
                    )
                    return sectors
                elif "sectors" in data and isinstance(data["sectors"], list):
                    # If only sectors field exists
                    sectors = data["sectors"]
                    logger.info(
                        "Successfully retrieved %d sectors from direct field",
                        len(sectors),
                    )
                    return sectors
                elif "entries" in data and isinstance(data["entries"], list):
                    # If only entries field exists
                    sectors = data["entries"]
                    logger.info(
                        "Successfully retrieved %d sectors from direct entries field",
                        len(sectors),
                    )
                    return sectors
                else:
                    # If we can't find sectors in the expected structure, log the full response for debugging
                    logger.error(
                        "Could not find sectors in response structure. Full response: %s",
                        data,
                    )
                    error_msg = data.get(
                        "error", "Unknown error - check API response format"
                    )
                    logger.error("Error in API response: %s", error_msg)
                    return f"Error fetching sectors: {error_msg}"

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %d - %s", e.response.status_code, e.response.text)
            return f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            logger.error("Request error: %s", str(e))
            return f"Request error occurred: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error occurred")
            return f"An unexpected error occurred: {str(e)}"
