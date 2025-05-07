import logging
from typing import Optional, Type

from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill, SkillContext

logger = logging.getLogger(__name__)


class VeniceAudioBaseTool(IntentKitSkill):
    """Base class for Venice Audio tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )
    voice_model: str = Field(
        description="REQUIRED identifier for the specific Venice AI voice model to use for TTS generation (e.g., 'af_sky', 'am_echo'). This must be set per tool instance."
    )

    @property
    def category(self) -> str:
        return "venice_audio"

    def get_api_key(self, context: SkillContext) -> Optional[str]:
        """Gets Venice AI API Key, checking agent and system configs."""
        category_config = context.config  # Config specific to 'venice_audio' category
        agent_api_key = category_config.get("api_key")
        if agent_api_key:
            # Use self.name which is 'venice_audio_text_to_speech' here. Could use category for logging too.
            logger.debug(
                f"Using agent-specific Venice API key for audio skill {self.name} (Voice: {self.voice_model})"
            )
            return agent_api_key

        # Check system config for category-specific key, then generic key
        system_api_key = self.skill_store.get_system_config(
            f"{self.category}_api_key"
        ) or self.skill_store.get_system_config("venice_api_key")
        if system_api_key:
            logger.debug(
                f"Using system Venice API key for audio skill {self.name} (Voice: {self.voice_model})"
            )
            return system_api_key

        logger.warning(
            f"No Venice API key found in agent ({self.category}) or system config for skill {self.name}"
        )
        # Let _arun handle the missing key error if it's critical
        return None

    async def apply_rate_limit(self, context: SkillContext) -> None:
        """
        Applies rate limiting ONLY if specified in the agent's config ('skill_config').
        Checks for 'rate_limit_number' and 'rate_limit_minutes'.
        If not configured, NO rate limiting is applied.
        Raises ConnectionAbortedError if the configured limit is exceeded.
        """
        skill_config = context.config
        user_id = context.user_id

        # Get agent-specific limits safely
        limit_num = skill_config.get("rate_limit_number")
        limit_min = skill_config.get("rate_limit_minutes")

        # Apply limit ONLY if both values are present and valid (truthy check handles None and 0)
        if limit_num and limit_min:
            limit_source = "Agent"
            logger.debug(
                f"Applying {limit_source} rate limit ({limit_num}/{limit_min} min) for user {user_id} on {self.name} (Voice: {self.voice_model})"
            )
            # This call might raise ConnectionAbortedError if the limit is hit
            await self.user_rate_limit_by_category(user_id, limit_num, limit_min)
        else:
            # No valid agent configuration found, so do nothing.
            logger.debug(
                f"No agent rate limits configured for category '{self.category}'. Skipping rate limit for user {user_id}."
            )
