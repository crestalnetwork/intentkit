import logging

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.models.tool import AgentToolData
from intentkit.tools.crw.base import CrwBaseTool

logger = logging.getLogger(__name__)


class CrwClearInput(BaseModel):
    """Input for fastCRW clear tool."""

    confirm: bool = Field(
        description="Must be true to confirm deletion.",
        default=False,
    )


class CrwClearIndexedContent(CrwBaseTool):
    """Tool for clearing all indexed fastCRW content.

    This tool removes all previously indexed content from the fastCRW vector store,
    allowing for a fresh start with new content.
    """

    name: str = "crw_clear_indexed_content"
    description: str = "Permanently clear all indexed fastCRW content from the vector store. Cannot be undone."
    args_schema: ArgsSchema | None = CrwClearInput

    async def _arun(
        self,
        confirm: bool = False,
        **kwargs,
    ) -> str:
        """Clear all indexed fastCRW content for the agent.

        Args:
            confirm: Must be True to confirm the deletion
            config: The configuration for the tool call

        Returns:
            str: Confirmation message
        """
        context = self.get_context()
        agent_id = context.agent_id

        if not agent_id:
            raise ToolException("Error: Agent ID not available for clearing content.")
        if not confirm:
            raise ToolException(
                "Error: You must set confirm=true to clear all indexed content."
            )
        logger.info(
            f"crw_clear: Starting clear indexed content operation for agent {agent_id}"
        )

        try:
            # Delete vector store data (using web_scraper storage format for compatibility)
            vector_store_key = f"vector_store_{agent_id}"
            await AgentToolData.delete(agent_id, "web_scraper", vector_store_key)

            # Delete metadata
            metadata_key = f"indexed_urls_{agent_id}"
            await AgentToolData.delete(agent_id, "web_scraper", metadata_key)

            logger.info(
                f"crw_clear: Successfully cleared all indexed content for agent {agent_id}"
            )
            return "Successfully cleared all fastCRW indexed content. The vector store is now empty and ready for new content."

        except Exception as e:
            logger.error(
                f"crw_clear: Error clearing indexed content for agent {agent_id}: {e}",
                exc_info=True,
            )
            raise ToolException(f"Error clearing indexed content: {str(e)}")
