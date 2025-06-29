import logging
from typing import Optional, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)


class CookieFunBaseTool(IntentKitSkill):
    """Base class for CookieFun tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    @property
    def category(self) -> str:
        return "cookiefun"

    def get_api_key(self, config: RunnableConfig) -> Optional[str]:
        """
        Get the API key from configuration.

        Args:
            config: The runnable configuration containing context

        Returns:
            The API key or None if not configured
        """
        context = self.context_from_config(config)
        skill_config = context.config
        if skill_config.get("api_key_provider") == "agent_owner":
            return skill_config.get("api_key")
        return self.skill_store.get_system_config("cookiefun_api_key")
