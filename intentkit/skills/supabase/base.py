from typing import Type

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
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

    def get_supabase_config(self, context: AgentContext) -> tuple[str, str]:
        """Get Supabase URL and key from config.

        Args:
            config: The agent configuration
            context: The skill context containing configuration and mode info

        Returns:
            Tuple of (supabase_url, supabase_key)

        Raises:
            ValueError: If required config is missing
        """
        config = context.agent.skill_config(self.category)
        supabase_url = config.get("supabase_url")

        # Use public_key for public operations if available, otherwise fall back to supabase_key
        if context.is_private:
            supabase_key = config.get("supabase_key")
        else:
            # Try public_key first, fall back to supabase_key if public_key doesn't exist
            supabase_key = config.get("public_key") or config.get("supabase_key")

        if not supabase_url:
            raise ValueError("supabase_url is required in config")
        if not supabase_key:
            raise ValueError("supabase_key is required in config")

        return supabase_url, supabase_key

    def validate_table_access(self, table: str, context: AgentContext) -> None:
        """Validate if the table can be accessed for write operations in public mode.

        Args:
            table: The table name to validate
            context: The skill context containing configuration and mode info

        Raises:
            ToolException: If table access is not allowed in public mode
        """
        # If in private mode (owner mode), no restrictions apply
        if context.is_private:
            return

        config = context.agent.skill_config(self.category)

        # In public mode, check if table is in allowed list
        public_write_tables = config.get("public_write_tables", "")
        if not public_write_tables:
            return

        allowed_tables = [
            t.strip() for t in public_write_tables.split(",") if t.strip()
        ]
        if table not in allowed_tables:
            raise ToolException(
                f"Table '{table}' is not allowed for public write operations. "
                f"Allowed tables: {', '.join(allowed_tables)}"
            )
