import logging
from typing import Type

from langchain_core.runnables import RunnableConfig
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
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Query the indexed Firecrawl content."""
        try:
            # Get agent context - throw error if not available
            if not config:
                raise ValueError("Configuration is required but not provided")

            context = self.context_from_config(config)
            if not context or not context.agent or not context.agent.id:
                raise ValueError("Agent ID is required but not found in configuration")

            agent_id = context.agent.id

            logger.info(f"[{agent_id}] Starting Firecrawl query operation: '{query}'")

            # Use the same vector store as web_scraper since we're indexing to the same store
            vector_store_key = f"vector_store_{agent_id}"

            logger.info(f"[{agent_id}] Looking for vector store: {vector_store_key}")

            stored_data = await self.skill_store.get_agent_skill_data(
                agent_id, "web_scraper", vector_store_key
            )

            if not stored_data:
                logger.warning(f"[{agent_id}] No vector store found")
                return "No indexed content found. Please use the firecrawl_scrape or firecrawl_crawl tools first to scrape and index some web content before querying."

            if not stored_data or "faiss_files" not in stored_data:
                logger.warning(f"[{agent_id}] Invalid stored data structure")
                return "No indexed content found. Please use the firecrawl_scrape or firecrawl_crawl tools first to scrape and index some web content before querying."

            # Import vector store utilities from web_scraper
            from intentkit.skills.web_scraper.utils import (
                DocumentProcessor,
                VectorStoreManager,
            )

            # Create embeddings and decode vector store
            logger.info(f"[{agent_id}] Decoding vector store")
            vs_manager = VectorStoreManager(self.skill_store)
            embeddings = vs_manager.create_embeddings()
            vector_store = vs_manager.decode_vector_store(
                stored_data["faiss_files"], embeddings
            )

            logger.info(
                f"[{agent_id}] Vector store loaded, index count: {vector_store.index.ntotal}"
            )

            # Perform similarity search
            docs = vector_store.similarity_search(query, k=max_results)
            logger.info(f"[{agent_id}] Found {len(docs)} similar documents")

            if not docs:
                logger.info(f"[{agent_id}] No relevant documents found for query")
                return f"No relevant information found for your query: '{query}'. The indexed content may not contain information related to your search."

            # Format results
            results = []
            for i, doc in enumerate(docs, 1):
                # Sanitize content to prevent database storage errors
                content = DocumentProcessor.sanitize_for_database(
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
                if config:
                    context = self.context_from_config(config)
                    if context and context.agent and context.agent.id:
                        agent_id = context.agent.id
            except Exception:
                pass

            logger.error(
                f"[{agent_id}] Error in FirecrawlQueryIndexedContent: {e}",
                exc_info=True,
            )
            raise type(e)(f"[agent:{agent_id}]: {e}") from e
