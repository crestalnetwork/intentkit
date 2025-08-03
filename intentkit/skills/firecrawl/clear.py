import logging
from typing import Type

from pydantic import BaseModel, Field

from intentkit.skills.firecrawl.base import FirecrawlBaseTool

logger = logging.getLogger(__name__)


class FirecrawlClearInput(BaseModel):
    """Input for Firecrawl clear tool."""

    confirm: bool = Field(
        description="Confirmation to clear all indexed content (must be true)",
        default=False,
    )


class FirecrawlClearIndexedContent(FirecrawlBaseTool):
    """Tool for clearing all indexed Firecrawl content.

    This tool removes all previously indexed content from the Firecrawl vector store,
    allowing for a fresh start with new content.
    """

    name: str = "firecrawl_clear_indexed_content"
    description: str = (
        "Clear all previously indexed Firecrawl content from the vector store.\n"
        "This will permanently delete all indexed content and cannot be undone.\n"
        "Use this tool when you want to start fresh with new content."
    )
    args_schema: Type[BaseModel] = FirecrawlClearInput

    async def _arun(
        self,
        confirm: bool = False,
        **kwargs,
    ) -> str:
        """Clear all indexed Firecrawl content for the agent.

        Args:
            confirm: Must be True to confirm the deletion
            config: The configuration for the tool call

        Returns:
            str: Confirmation message
        """
        context = self.get_context()
        agent_id = context.agent_id

        if not agent_id:
            return "Error: Agent ID not available for clearing content."

        if not confirm:
            return "Error: You must set confirm=true to clear all indexed content."

        logger.info(
            f"firecrawl_clear: Starting clear indexed content operation for agent {agent_id}"
        )

        try:
            # Delete vector store data (using web_scraper storage format for compatibility)
            vector_store_key = f"vector_store_{agent_id}"
            await self.skill_store.delete_agent_skill_data(
                agent_id, "web_scraper", vector_store_key
            )

            # Delete metadata
            metadata_key = f"indexed_urls_{agent_id}"
            await self.skill_store.delete_agent_skill_data(
                agent_id, "web_scraper", metadata_key
            )

            logger.info(
                f"firecrawl_clear: Successfully cleared all indexed content for agent {agent_id}"
            )
            return "Successfully cleared all Firecrawl indexed content. The vector store is now empty and ready for new content."

        except Exception as e:
            logger.error(
                f"firecrawl_clear: Error clearing indexed content for agent {agent_id}: {e}",
                exc_info=True,
            )
            return f"Error clearing indexed content: {str(e)}"
