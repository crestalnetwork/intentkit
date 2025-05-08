import logging
from typing import Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.cookiefun.base import CookieFunBaseTool

logger = logging.getLogger(__name__)


class GetCountryTimeInput(BaseModel):
    """Input for GetCountryTime tool."""

    country: str = Field(
        description="Name of the country to get time for (e.g. 'germany', 'france')"
    )


class GetCountryTime(CookieFunBaseTool):
    """Tool for getting current time in different timezones of a country."""

    name: str = "cookiefun_get_country_time"
    description: str = (
        "Get the current time in different timezones of a specified country.\n"
        "Use this when you need to know the current time in a specific country."
    )
    args_schema: Type[BaseModel] = GetCountryTimeInput

    async def _arun(self, country: str, config: RunnableConfig = None, **kwargs) -> str:
        """Get country time from Cookie.fun API."""
        context = self.context_from_config(config)
        api_key = context.config.get("api_key")
        if not api_key:
            return "Error: Cookie.fun API key not configured"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.cookie-api.com/api/time/country-to-time",
                    params={"country": country},
                    headers={"Authorization": api_key},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                result = [f"Time in {data['country_name']} ({data['country_code']}):"]

                for tz, time in data["timezones"].items():
                    result.append(f"{tz}: {time}")

                return "\n".join(result)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error when fetching time for {country}: {str(e)}")
            return f"Error fetching time data: {str(e)}"
        except Exception as e:
            logger.error(f"Error getting time for {country}: {str(e)}")
            return f"Unexpected error: {str(e)}"
