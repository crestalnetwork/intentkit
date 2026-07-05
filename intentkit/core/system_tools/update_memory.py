"""Tool for updating the agent's scoped long-term memories."""

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_tools.base import SystemTool
from intentkit.models.memory import MemoryScopeLiteral


class UpdateMemoryInput(BaseModel):
    """Input schema for updating a scoped memory."""

    scope: MemoryScopeLiteral = Field(
        ...,
        description=(
            "Which memory to update. Use the scopes listed in your Memory "
            "section: 'team' for facts shared with the whole team, and the "
            "conversation-specific scope ('user', 'channel' or 'cron') for "
            "facts about this counterpart or task."
        ),
    )
    content: str = Field(..., description="New information to merge into that memory")


class UpdateMemoryTool(SystemTool):
    """Tool for adding or updating one of the agent's scoped memories.

    Merges new information into the selected memory document using an LLM to
    consolidate and deduplicate. The available scopes depend on the
    conversation (resolved from the agent context); updating a scope that is
    not active in this conversation is rejected.
    """

    name: str = "update_memory"
    description: str = (
        "Add or update one of your memories. Pick the scope from your Memory "
        "section ('team' plus this conversation's 'user'/'channel'/'cron') "
        "and provide the new information to remember."
    )
    args_schema: ArgsSchema | None = UpdateMemoryInput

    @override
    async def _arun(self, scope: str, content: str) -> str:
        from intentkit.core.memory import resolve_memory_scopes, update_scoped_memory

        context = self.get_context()
        if context.is_subagent:
            raise ToolException(
                "Memory is not available in sub-agent runs: the entry agent "
                "owns the conversation's memory."
            )

        scopes = {s.scope: s for s in resolve_memory_scopes(context.agent, context)}
        target = scopes.get(scope)
        if target is None:
            raise ToolException(
                f"Memory scope '{scope}' is not active in this conversation. "
                f"Active scopes: {', '.join(sorted(scopes))}."
            )

        try:
            updated = await update_scoped_memory(
                context.agent_id, target.scope, target.scope_key, content
            )
        except ToolException:
            raise
        except Exception as e:
            self.logger.error("update_memory failed: %s", e, exc_info=True)
            raise ToolException(f"Failed to update memory: {e}") from e
        return f"{target.heading} updated successfully. Current content:\n{updated}"
