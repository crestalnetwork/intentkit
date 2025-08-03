import logging
from typing import Type

from pydantic import BaseModel, Field

from intentkit.skills.firecrawl.base import FirecrawlBaseTool

logger = logging.getLogger(__name__)


class FirecrawlQueryInput(BaseModel):
    """Input for Firecrawl query tool."""

    query: str = Field(
        description="Question or query to search in the indexed content",
        min_length=1,
        max_length=500,
    )
    max_results: int = Field(
        description="Maximum number of relevant documents to return (default: 4)",
        default=4,
        ge=1,
        le=10,
    )


class FirecrawlQueryIndexedContent(FirecrawlBaseTool):
    """Tool for querying previously indexed Firecrawl content.

    This tool searches through content that was previously scraped and indexed
    using the firecrawl_scrape or firecrawl_crawl tools to answer questions or find relevant information.
    """

    name: str = "firecrawl_query_indexed_content"
    description: str = (
        "Query previously indexed Firecrawl content to find relevant information and answer questions.\n"
        "Use this tool to search through content that was previously scraped and indexed using Firecrawl tools.\n"
        "This tool can help answer questions based on the indexed web content from Firecrawl scraping/crawling."
    )
    args_schema: Type[BaseModel] = FirecrawlQueryInput

    async def _arun(
        self,
        query: str,
        max_results: int = 4,
        **kwargs,
    ) -> str:
        """Query the indexed Firecrawl content."""
        try:
            # Get agent context - throw error if not available
            # Configuration is always available in new runtime
            pass

            context = self.get_context()
            if not context or not context.agent_id:
                raise ValueError("Agent ID is required but not found in configuration")

            agent_id = context.agent_id

            logger.info(f"[{agent_id}] Starting Firecrawl query operation: '{query}'")

            # Import query utilities from firecrawl utils
            from intentkit.skills.firecrawl.utils import (
                FirecrawlDocumentProcessor,
                query_indexed_content,
            )

            # Query the indexed content
            docs = await query_indexed_content(
                query, agent_id, self.skill_store, max_results
            )

            if not docs:
                logger.info(f"[{agent_id}] No relevant documents found for query")
                return f"No relevant information found for your query: '{query}'. The indexed content may not contain information related to your search."

            # Format results
            results = []
            for i, doc in enumerate(docs, 1):
                # Sanitize content to prevent database storage errors
                content = FirecrawlDocumentProcessor.sanitize_for_database(
                    doc.page_content.strip()
                )
                source = doc.metadata.get("source", "Unknown")
                source_type = doc.metadata.get("source_type", "unknown")

                # Add source type indicator for Firecrawl content
                if source_type.startswith("firecrawl"):
                    source_indicator = (
                        f"[Firecrawl {source_type.replace('firecrawl_', '').title()}]"
                    )
                else:
                    source_indicator = ""

                results.append(
                    f"**Source {i}:** {source} {source_indicator}\n{content}"
                )

            response = "\n\n".join(results)
            logger.info(
                f"[{agent_id}] Firecrawl query completed successfully, returning {len(response)} chars"
            )

            return response

        except Exception as e:
            # Extract agent_id for error logging if possible
            agent_id = "UNKNOWN"
            try:
                # TODO: Fix config reference
                context = self.get_context()
                if context and context.agent_id:
                    agent_id = context.agent_id
            except Exception:
                pass

            logger.error(
                f"[{agent_id}] Error in FirecrawlQueryIndexedContent: {e}",
                exc_info=True,
            )
            raise type(e)(f"[agent:{agent_id}]: {e}") from e
