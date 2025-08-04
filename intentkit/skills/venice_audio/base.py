import logging
from typing import Dict, List, Optional, Tuple, Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)


class VeniceAudioBaseTool(IntentKitSkill):
    """Base class for Venice Audio tools."""

    name: str = Field(default="venice_base_tool", description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]  # type: ignore
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    @property
    def category(self) -> str:
        return "venice_audio"

    def validate_voice_model(
        self, context, voice_model: str
    ) -> Tuple[bool, Optional[Dict[str, object]]]:
        config = context.config

        selected_model = config.get("voice_model")
        custom_models = config.get("voice_model_custom", [])

        allowed_voice_models: List[str] = []

        if selected_model == "custom":
            allowed_voice_models = custom_models or []
        else:
            allowed_voice_models = [selected_model] if selected_model else []

        if voice_model not in allowed_voice_models:
            return False, {
                "error": f'"{voice_model}" is not allowed',
                "allowed": allowed_voice_models,
                "suggestion": "please try again with allowed voice model",
            }

        return True, None

    def get_api_key(self) -> str:
        """
        Retrieves the Venice AI API key based on the api_key_provider setting.

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
                agent_api_key = skill_config.get("api_key")
                if agent_api_key:
                    logger.debug(
                        f"Using agent-specific Venice API key for skill {self.name} in category {self.category}"
                    )
                    return agent_api_key
                raise ToolException(
                    f"No agent-owned Venice API key found for skill '{self.name}' in category '{self.category}'."
                )

            elif api_key_provider == "platform":
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
                    f"Invalid API key provider '{api_key_provider}' for skill '{self.name}'"
                )

        except Exception as e:
            raise ToolException(f"Failed to retrieve Venice API key: {str(e)}") from e

    async def apply_rate_limit(self, context) -> None:
        """
        Applies rate limiting ONLY if specified in the agent's config ('skill_config').
        Checks for 'rate_limit_number' and 'rate_limit_minutes'.
        If not configured, NO rate limiting is applied.
        Raises ConnectionAbortedError if the configured limit is exceeded.
        """
        skill_config = context.agent.skill_config(self.category)
        user_id = context.agent.id

        # Get agent-specific limits safely
        limit_num = skill_config.get("rate_limit_number")
        limit_min = skill_config.get("rate_limit_minutes")

        # Apply limit ONLY if both values are present and valid (truthy check handles None and 0)
        if limit_num and limit_min:
            limit_source = "Agent"
            logger.debug(
                f"Applying {limit_source} rate limit ({limit_num}/{limit_min} min) for user {user_id} on {self.name}"
            )
            if user_id:
                await self.user_rate_limit_by_category(user_id, limit_num, limit_min)
        else:
            # No valid agent configuration found, so do nothing.
            logger.debug(
                f"No agent rate limits configured for category '{self.category}'. Skipping rate limit for user {user_id}."
            )
