import logging

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.crw.base import CrwBaseTool

logger = logging.getLogger(__name__)


class CrwQueryInput(BaseModel):
    """Input for fastCRW query tool."""

    query: str = Field(
        description="Search query for indexed content.",
        min_length=1,
        max_length=500,
    )
    max_results: int = Field(
        description="Max relevant documents to return.",
        default=4,
        ge=1,
        le=10,
    )


class CrwQueryIndexedContent(CrwBaseTool):
    """Tool for querying previously indexed fastCRW content.

    This tool searches through content that was previously scraped and indexed
    using the crw_scrape or crw_crawl tools to answer questions or find relevant information.
    """

    name: str = "crw_query_indexed_content"
    description: str = (
        "Search previously indexed fastCRW content to find relevant information."
    )
    args_schema: ArgsSchema | None = CrwQueryInput

    async def _arun(
        self,
        query: str,
        max_results: int = 4,
        **kwargs,
    ) -> str:
        """Query the indexed fastCRW content."""
        try:
            context = self.get_context()
            if not context or not context.agent_id:
                raise ToolException(
                    "Agent ID is required but not found in configuration"
                )

            agent_id = context.agent_id

            logger.info(
                "[%s] Starting fastCRW query operation: '%s'", agent_id, query
            )

            # Import query utilities from crw utils
            from intentkit.tools.crw.utils import (
                CrwDocumentProcessor,
                CrwVectorStoreManager,
                query_indexed_content,
            )

            # Query the indexed content
            vector_manager = CrwVectorStoreManager()
            docs = await query_indexed_content(
                query, agent_id, vector_manager, max_results
            )

            if not docs:
                logger.info("[%s] No relevant documents found for query", agent_id)
                return f"No relevant information found for your query: '{query}'. The indexed content may not contain information related to your search."

            # Format results
            results = []
            for i, doc in enumerate(docs, 1):
                # Sanitize content to prevent database storage errors
                content = CrwDocumentProcessor.sanitize_for_database(
                    doc.page_content.strip()
                )
                source = doc.metadata.get("source", "Unknown")
                source_type = doc.metadata.get("source_type", "unknown")

                # Add source type indicator for fastCRW content
                if source_type.startswith("crw"):
                    source_indicator = (
                        f"[fastCRW {source_type.replace('crw_', '').title()}]"
                    )
                else:
                    source_indicator = ""

                results.append(
                    f"**Source {i}:** {source} {source_indicator}\n{content}"
                )

            response = "\n\n".join(results)
            logger.info(
                f"[{agent_id}] fastCRW query completed successfully, returning {len(response)} chars"
            )

            return response

        except ToolException:
            raise
        except Exception as e:
            logger.error("Error in CrwQueryIndexedContent: %s", e, exc_info=True)
            raise ToolException(f"Failed to query indexed content: {e!s}")
