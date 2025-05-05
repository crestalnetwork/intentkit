import logging
from typing import Optional

from pydantic import Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill, SkillContext

logger = logging.getLogger(__name__)

base_url = "https://api.venice.ai"  # Common base URL for all Venice endpoints


class VeniceImageBaseTool(IntentKitSkill):
    """
    Generic base class for tools interacting with the Venice AI API.
    Handles shared logic like API key retrieval and rate limiting.
    Subclasses should define specific API interactions.
    """

    @property
    def category(self) -> str:
        return "venice_image"

    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data and configs."
    )

    def get_api_key(self, context: SkillContext) -> Optional[str]:
        """Get the API key, prioritizing agent config then system config."""
        # Check agent config first for the specific skill's category
        category_config = context.config  # Config specific to this skill's category
        agent_api_key = category_config.get("api_key")

        if agent_api_key:
            logger.debug(
                f"Using agent-specific Venice API key for skill {self.name} in category {self.category}"
            )
            return agent_api_key

        # Fallback to system config (assuming a single system key for all Venice)
        # If different Venice services need different system keys, this needs adjustment.
        system_api_key = self.skill_store.get_system_config("venice_api_key")
        if system_api_key:
            logger.debug(
                f"Using system Venice API key for skill {self.name} in category {self.category}"
            )
            return system_api_key

        logger.warning(
            f"No Venice API key found in agent ({self.category}) or system config for skill {self.name}"
        )
        return None

    async def apply_rate_limit(self, context: SkillContext) -> None:
        """
        Applies rate limiting based on agent or system configuration
        for the skill's category.
        """
        skill_category_config = context.config  # Config for this skill's category
        using_agent_key = (
            "api_key" in skill_category_config and skill_category_config["api_key"]
        )

        agent_rate_limit_num = skill_category_config.get("rate_limit_number")
        agent_rate_limit_min = skill_category_config.get("rate_limit_minutes")

        if using_agent_key and agent_rate_limit_num and agent_rate_limit_min:
            logger.debug(
                f"Applying agent rate limit ({agent_rate_limit_num}/{agent_rate_limit_min} min) "
                f"for user {context.user_id} on skill category {self.category}"
            )
            # Apply limit per user, per category
            await self.user_rate_limit_by_category(
                context.user_id, agent_rate_limit_num, agent_rate_limit_min
            )
        elif not using_agent_key:
            # Try system rate limits (these might need to be category-specific in system config too)
            # Example: venice_image_rate_limit_number, venice_text_rate_limit_number
            sys_rate_limit_num = self.skill_store.get_system_config(
                f"venice_{self.category}_rate_limit_number"
            )
            sys_rate_limit_min = self.skill_store.get_system_config(
                f"venice_{self.category}_rate_limit_minutes"
            )

            # Fallback to generic Venice system limits if category-specific aren't found
            if not (sys_rate_limit_num and sys_rate_limit_min):
                sys_rate_limit_num = self.skill_store.get_system_config(
                    "venice_rate_limit_number",
                    10,  # Example default
                )
                sys_rate_limit_min = self.skill_store.get_system_config(
                    "venice_rate_limit_minutes",
                    1440,  # Example default (1 day)
                )

            if sys_rate_limit_num and sys_rate_limit_min:
                logger.debug(
                    f"Applying system rate limit ({sys_rate_limit_num}/{sys_rate_limit_min} min) "
                    f"for user {context.user_id} on skill category {self.category}"
                )
                # Apply limit per user, per category
                await self.user_rate_limit_by_category(
                    context.user_id, sys_rate_limit_num, sys_rate_limit_min
                )
            else:
                logger.warning(
                    f"System rate limits for Venice AI category '{self.category}' not configured. "
                    f"Applying fallback 10 requests/day for user {context.user_id}."
                )
                # Apply limit per user, per category
                await self.user_rate_limit_by_category(context.user_id, 10, 1440)
