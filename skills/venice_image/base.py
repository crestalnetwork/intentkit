import logging
from typing import Any, Dict, Optional, Tuple

from pydantic import Field

from skills.base import IntentKitSkill, SkillContext, SkillStoreABC, ToolException
from skills.venice_image.api import (
    make_venice_api_request,
)
from skills.venice_image.config import VeniceImageConfig

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

    def getSkillConfig(self, context: SkillContext) -> VeniceImageConfig:
        """
        Creates a VeniceImageConfig instance from a dictionary of configuration values.

        Args:
            config: A dictionary containing configuration settings.

        Returns:
            A VeniceImageConfig object.
        """

        return VeniceImageConfig(
            api_key_provider=context.config.get("api_key_provider", "agent_owner"),
            safe_mode=context.config.get("safe_mode", True),
            hide_watermark=context.config.get("hide_watermark", True),
            embed_exif_metadata=context.config.get("embed_exif_metadata", False),
            negative_prompt=context.config.get(
                "negative_prompt", "(worst quality: 1.4), bad quality, nsfw"
            ),
            rate_limit_number=context.config.get("rate_limit_number"),
            rate_limit_minutes=context.config.get("rate_limit_minutes"),
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
            skillConfig = self.getSkillConfig(context=context)
            if skillConfig.api_key_provider == "agent_owner":
                agent_api_key = context.config.get("api_key")
                if agent_api_key:
                    logger.debug(
                        f"Using agent-specific Venice API key for skill {self.name} in category {self.category}"
                    )
                    return agent_api_key
                raise ToolException(
                    f"No agent-owned Venice API key found for skill '{self.name}' in category '{self.category}'."
                )

            elif skillConfig.api_key_provider == "platform":
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
                    f"Invalid API key provider '{skillConfig.api_key_provider}' for skill '{self.name}'"
                )

        except Exception as e:
            raise ToolException(f"Failed to retrieve Venice API key: {str(e)}") from e

    async def apply_venice_rate_limit(self, context: SkillContext) -> None:
        """
        Applies rate limiting to prevent exceeding the Venice AI API's rate limits.

        Rate limits are applied based on the api_key_provider setting:
            - 'agent_owner': uses agent-specific configuration.
            - 'platform': uses system-wide configuration.
        """
        try:
            user_id = context.user_id
            skillConfig = self.getSkillConfig(context=context)

            if skillConfig.api_key_provider == "agent_owner":
                limit_num = skillConfig.rate_limit_number
                limit_min = skillConfig.rate_limit_minutes

                if limit_num and limit_min:
                    logger.debug(
                        f"Applying Agent rate limit ({limit_num}/{limit_min} min) for user {user_id} on {self.name}"
                    )
                    await self.user_rate_limit_by_category(
                        user_id, limit_num, limit_min
                    )

            elif skillConfig.api_key_provider == "platform":
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
