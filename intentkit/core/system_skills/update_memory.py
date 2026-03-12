"""Skill for updating agent long-term memory."""

from typing import override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_skills.base import SystemSkill


class UpdateMemoryInput(BaseModel):
    """Input schema for updating long-term memory."""

    content: str = Field(
        ..., description="New memory content to merge into long-term memory"
    )


class UpdateMemorySkill(SystemSkill):
    """Skill for adding or updating the agent's long-term memory.

    This skill merges new information into the agent's existing long-term
    memory using an LLM to consolidate and deduplicate.
    """

    name: str = "update_memory"
    description: str = (
        "Add or update your long-term memory. Provide the new information to remember."
    )
    args_schema: ArgsSchema | None = UpdateMemoryInput

    @override
    async def _arun(self, content: str) -> str:
        """Update the agent's long-term memory.

        Args:
            content: New information to merge into memory.

        Returns:
            A message with the updated memory content.
        """
        try:
            from intentkit.core.memory import update_memory

            context = self.get_context()
            agent_id = context.agent_id
            updated = await update_memory(agent_id, content)
            return f"Memory updated successfully. Current memory:\n{updated}"
        except ToolException:
            raise
        except Exception as e:
            self.logger.error(f"update_memory failed: {e}", exc_info=True)
            raise ToolException(f"Failed to update memory: {e}") from e
