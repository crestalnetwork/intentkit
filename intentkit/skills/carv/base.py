import logging
from typing import Any, Dict, Optional, Tuple, Type

import httpx  # Ensure httpx is installed: pip install httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)

CARV_API_BASE_URL = "https://interface.carv.io"


class CarvBaseTool(IntentKitSkill):
    """Base class for CARV API tools."""

    name: str = Field(description="Tool name")  # type: ignore
    description: str = Field(description="Tool description")
    args_schema: Type[BaseModel]  # type: ignore
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    @property
    def category(self) -> str:
        return "carv"

    def get_api_key(self) -> str:
        """
        Retrieves the CARV API key based on the api_key_provider setting.

        Returns:
            The API key if found.

        Raises:
            ToolException: If the API key is not found or provider is invalid.
        """
        try:
            context = self.get_context()
            skill_config = context.agent.skill_config(self.category)
            api_key_provider = skill_config.get("api_key_provider")
            if api_key_provider == "agent_owner":
                agent_api_key: Optional[str] = skill_config.get("api_key")
                if agent_api_key:
                    logger.debug(
                        f"Using agent-specific CARV API key for skill {self.name} in category {self.category}"
                    )
                    return agent_api_key
                raise ToolException(
                    f"No agent-owned CARV API key found for skill '{self.name}' in category '{self.category}'."
                )

            elif api_key_provider == "platform":
                system_api_key = self.skill_store.get_system_config("carv_api_key")
                if system_api_key:
                    logger.debug(
                        f"Using system CARV API key for skill {self.name} in category {self.category}"
                    )
                    return system_api_key
                raise ToolException(
                    f"No platform-hosted CARV API key found for skill '{self.name}' in category '{self.category}'."
                )

            else:
                raise ToolException(
                    f"Invalid API key provider '{api_key_provider}' for skill '{self.name}'"
                )

        except Exception as e:
            # Re-raise ToolException if it's already one, otherwise wrap
            if isinstance(e, ToolException):
                raise
            raise ToolException(f"Failed to retrieve CARV API key: {str(e)}") from e

    async def apply_rate_limit(self, context) -> None:
        """
        Applies rate limiting ONLY if specified in the agent's config ('skill_config').
        Checks for 'rate_limit_number' and 'rate_limit_minutes'.
        If not configured, NO rate limiting is applied.
        Raises ConnectionAbortedError if the configured limit is exceeded.
        """
        skill_config = context.agent.skill_config(self.category)
        user_id = context.agent.id

        limit_num = skill_config.get("rate_limit_number")
        limit_min = skill_config.get("rate_limit_minutes")

        # Apply limit ONLY if both values are present and valid (truthy check handles None and 0)
        if limit_num and limit_min:
            logger.debug(
                f"Applying rate limit ({limit_num}/{limit_min} min) for user {user_id} on {self.name}"
            )
            if user_id:
                await self.user_rate_limit_by_category(user_id, limit_num, limit_min)
        else:
            # No valid agent configuration found, so do nothing.
            logger.debug(
                f"No agent rate limits configured for category '{self.category}'. Skipping rate limit for user {user_id}."
            )

    async def _call_carv_api(
        self,
        context,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
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
