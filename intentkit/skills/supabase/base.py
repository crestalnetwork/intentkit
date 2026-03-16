import time

from langchain_core.tools import ToolException
from supabase import Client, create_client

from intentkit.abstracts.graph import AgentContext
from intentkit.skills.base import IntentKitSkill

# Cache Supabase clients per (url, key) pair with TTL
_supabase_clients: dict[str, Client] = {}
_supabase_clients_accessed_at: dict[str, float] = {}
_SUPABASE_CLIENT_CACHE_TTL = 3600  # 1 hour


def _cleanup_supabase_cache() -> None:
    """Evict expired Supabase client cache entries."""
    now = time.monotonic()
    for cache_key in list(_supabase_clients_accessed_at):
        if now - _supabase_clients_accessed_at[cache_key] > _SUPABASE_CLIENT_CACHE_TTL:
            _supabase_clients.pop(cache_key, None)
            _supabase_clients_accessed_at.pop(cache_key, None)


def get_cached_supabase_client(url: str, key: str) -> Client:
    """Get or create a cached Supabase client."""
    _cleanup_supabase_cache()
    cache_key = f"{url}:{key}"
    if cache_key not in _supabase_clients:
        _supabase_clients[cache_key] = create_client(url, key)
    _supabase_clients_accessed_at[cache_key] = time.monotonic()
    return _supabase_clients[cache_key]


class SupabaseBaseTool(IntentKitSkill):
    """Base class for Supabase tools."""

    category: str = "supabase"

    def get_supabase_client(self, context: AgentContext) -> Client:
        """Get a cached Supabase client for the current context."""
        url, key = self.get_supabase_config(context)
        return get_cached_supabase_client(url, key)

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
            raise ToolException("supabase_url is required in config")
        if not supabase_key:
            raise ToolException("supabase_key is required in config")

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

        # In public mode, check if table is in allowed list.
        # NOTE: Empty/unset allowlist intentionally means allow-all — the agent
        # owner opts in by leaving it blank, so no default-deny is needed here.
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
