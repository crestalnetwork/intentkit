from typing import Type

from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill


class SupabaseBaseTool(IntentKitSkill):
    """Base class for Supabase tools."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    @property
    def category(self) -> str:
        return "supabase"

    def get_supabase_config(self, config: dict) -> tuple[str, str]:
        """Get Supabase URL and key from config.

        Args:
            config: The agent configuration

        Returns:
            Tuple of (supabase_url, supabase_key)

        Raises:
            ValueError: If required config is missing
        """
        supabase_url = config.get("supabase_url")
        supabase_key = config.get("supabase_key")

        if not supabase_url:
            raise ValueError("supabase_url is required in config")
        if not supabase_key:
            raise ValueError("supabase_key is required in config")

        return supabase_url, supabase_key
