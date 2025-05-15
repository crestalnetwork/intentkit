import logging
from typing import Any, Dict, Optional, Tuple

from pydantic import Field

from skills.base import IntentKitSkill, SkillContext, SkillStoreABC, ToolException
from skills.venice_image.api import (
    make_venice_api_request,
)

logger = logging.getLogger(__name__)

venice_base_url = "https://api.venice.ai"  # Common base URL for all Venice endpoints


class VeniceImageBaseTool(IntentKitSkill):
    """
    Base class for all Venice AI image-related skills.

    This class provides common functionality for interacting with the
    Venice AI API, including:

    -   Retrieving the API key (from agent or system configuration).
    -   Applying rate limits to prevent overuse of the API.
    -   A standardized `post` method for making API requests.

    Subclasses should inherit from this class and implement their specific
    API interactions (e.g., image generation, upscaling, inpainting)
    by defining their own `_arun` methods and setting appropriate `name`
    and `description` attributes.
    """

    @property
    def category(self) -> str:
        """
        Returns the category of this skill, used for configuration and logging.
        """
        return "venice_image"

    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data and configs."
    )
    api_key_provider: str = Field(
        default="agent_owner",
        description="provider of the API Key, could be agent_owner or platform_hosted",
    )
    safe_mode: bool = Field(
        default=True,
        description="Whether to use safe mode. If enabled, this will blur images that are classified as having adult content",
    )
    hide_watermark: bool = Field(
        default=True,
        description="Whether to hide the Venice watermark. Venice may ignore this parameter for certain generated content.",
    )
    embed_exif_metadata: bool = Field(
        default=False, description="Whether to embed EXIF metadata in the image."
    )
    negative_prompt: str = Field(
        default="(worst quality: 1.4), bad quality, nsfw",
        description="The default negative prompt used when no other prompt is provided.",
    )

    def get_api_key(self, context: SkillContext) -> str:
        """
        Retrieves the Venice AI API key based on the api_key_provider setting.

        Returns:
            The API key if found.

        Raises:
            ToolException: If the API key is not found or provider is invalid.
        """
        try:
            if self.api_key_provider == "agent_owner":
                agent_api_key = context.config.get("api_key")
                if agent_api_key:
                    logger.debug(
                        f"Using agent-specific Venice API key for skill {self.name} in category {self.category}"
                    )
                    return agent_api_key
                raise ToolException(
                    f"No agent-owned Venice API key found for skill '{self.name}' in category '{self.category}'."
                )

            elif self.api_key_provider == "platform_hosted":
                system_api_key = self.skill_store.get_system_config("venice_api_key")
                if system_api_key:
                    logger.debug(
                        f"Using system Venice API key for skill {self.name} in category {self.category}"
                    )
                    return system_api_key
                raise ToolException(
                    f"No platform-hosted Venice API key found for skill '{self.name}' in category '{self.category}'."
                )

            else:
                raise ToolException(
                    f"Invalid API key provider '{self.api_key_provider}' for skill '{self.name}'"
                )

        except Exception as e:
            raise ToolException(f"Failed to retrieve Venice API key: {str(e)}") from e

    async def apply_venice_rate_limit(self, context: SkillContext) -> None:
        """
        Applies rate limiting to prevent exceeding the Venice AI API's rate limits.

        Rate limits are applied based on the api_key_provider setting:
            - 'agent_owner': uses agent-specific configuration.
            - 'platform_hosted': uses system-wide configuration.
        """
        try:
            user_id = context.user_id

            if self.api_key_provider == "agent_owner":
                skill_config = context.config
                limit_num = skill_config.get("rate_limit_number")
                limit_min = skill_config.get("rate_limit_minutes")

                if limit_num and limit_min:
                    logger.debug(
                        f"Applying Agent rate limit ({limit_num}/{limit_min} min) for user {user_id} on {self.name}"
                    )
                    await self.user_rate_limit_by_category(
                        user_id, limit_num, limit_min
                    )

            elif self.api_key_provider == "platform_hosted":
                system_limit_num = self.skill_store.get_system_config(
                    f"{self.category}_rate_limit_number"
                )
                system_limit_min = self.skill_store.get_system_config(
                    f"{self.category}_rate_limit_minutes"
                )

                if system_limit_num and system_limit_min:
                    logger.debug(
                        f"Applying System rate limit ({system_limit_num}/{system_limit_min} min) for user {user_id} on {self.name}"
                    )
                    await self.user_rate_limit_by_category(
                        user_id, system_limit_num, system_limit_min
                    )
            # do nothing if no rate limit is
            return None

        except Exception as e:
            raise ToolException(f"Failed to apply Venice rate limit: {str(e)}") from e

    async def post(
        self, path: str, payload: Dict[str, Any], context: SkillContext
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Makes a POST request to the Venice AI API using the `make_venice_api_request`
        function from the `skills.venice_image.api` module.

        This method handles the following:

        1.  Retrieving the API key using `get_api_key`.
        2.  Constructing the request payload.
        3.  Calling `make_venice_api_request` to make the actual API call.
        4.  Returning the results from `make_venice_api_request`.

        Args:
            path: The API endpoint path (e.g., "/api/v1/image/generate").
            payload: The request payload as a dictionary.
            context: The SkillContext for accessing API keys and configs.

        Returns:
            A tuple: (success_data, error_data).
            - If successful, success contains the JSON response from the API.
            - If an error occurs, success is an empty dictionary, and error contains error details.
        """
        api_key = self.get_api_key(context)

        return await make_venice_api_request(
            api_key, path, payload, self.category, self.name
        )
