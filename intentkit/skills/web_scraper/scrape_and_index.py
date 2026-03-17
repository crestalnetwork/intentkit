import logging
from decimal import Decimal

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.web_scraper.base import WebScraperBaseTool
from intentkit.skills.web_scraper.utils import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    MetadataManager,
    ResponseFormatter,
    VectorStoreManager,
    scrape_and_index_urls,
)

logger = logging.getLogger(__name__)


class ScrapeAndIndexInput(BaseModel):
    """Input for ScrapeAndIndex tool."""

    urls: list[str] = Field(
        description="URLs to scrape (http/https).",
        min_length=1,
        max_length=25,
    )
    chunk_size: int = Field(
        description="Text chunk size for indexing.",
        default=DEFAULT_CHUNK_SIZE,
        ge=100,
        le=4000,
    )
    chunk_overlap: int = Field(
        description="Overlap between chunks.",
        default=DEFAULT_CHUNK_OVERLAP,
        ge=0,
        le=1000,
    )


class QueryIndexInput(BaseModel):
    """Input for QueryIndex tool."""

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


class ScrapeAndIndex(WebScraperBaseTool):
    """Tool for scraping web content and indexing it into a searchable vector store.

    This tool can scrape multiple URLs, process the content into chunks,
    and store it in a vector database for later retrieval and question answering.
    """

    name: str = "web_scraper_scrape_and_index"
    description: str = (
        "Scrape web URLs and index content into a vector store. "
        "Query later with query_indexed_content tool."
    )
    price: Decimal = Decimal("100")
    args_schema: ArgsSchema | None = ScrapeAndIndexInput

    async def _arun(
        self,
        urls: list[str],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        **kwargs,
    ) -> str:
        """Scrape URLs and index content into vector store."""
        try:
            # Get agent context - throw error if not available
            # Configuration is always available in new runtime
            pass

            context = self.get_context()
            if not context or not context.agent_id:
                raise ToolException(
                    "Agent ID is required but not found in configuration"
                )

            agent_id = context.agent_id

            logger.info(
                f"[{agent_id}] Starting scrape and index operation with {len(urls)} URLs"
            )

            embedding_api_key = self.get_openai_api_key()
            vector_manager = VectorStoreManager(embedding_api_key)

            # Use the utility function to scrape and index URLs
            total_chunks, was_merged, valid_urls = await scrape_and_index_urls(
                urls, agent_id, vector_manager, chunk_size, chunk_overlap
            )

            logger.info(
                "[%s] Scraping completed: %s chunks indexed, merged: %s",
                agent_id,
                total_chunks,
                was_merged,
            )

            if not valid_urls:
                logger.error("[%s] No valid URLs provided", agent_id)
                raise ToolException(
                    "Error: No valid URLs provided. URLs must start with http:// or https://"
                )
            if total_chunks == 0:
                logger.error("[%s] No content extracted from URLs", agent_id)
                raise ToolException(
                    "Error: No content could be extracted from the provided URLs."
                )
            # Get current storage size for response
            current_size = await vector_manager.get_content_size(agent_id)
            size_limit_reached = len(valid_urls) < len(urls)

            # Update metadata
            metadata_manager = MetadataManager(vector_manager)
            new_metadata = metadata_manager.create_url_metadata(
                valid_urls, [], "scrape_and_index"
            )
            await metadata_manager.update_metadata(agent_id, new_metadata)

            logger.info("[%s] Metadata updated successfully", agent_id)

            # Format response
            response = ResponseFormatter.format_indexing_response(
                "scraped and indexed",
                valid_urls,
                total_chunks,
                chunk_size,
                chunk_overlap,
                was_merged,
                current_size_bytes=current_size,
                size_limit_reached=size_limit_reached,
                total_requested_urls=len(urls),
            )

            logger.info(
                "[%s] Scrape and index operation completed successfully", agent_id
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

            logger.error("[%s] Error in ScrapeAndIndex: %s", agent_id, e, exc_info=True)
            raise type(e)(f"[agent:{agent_id}]: {e}") from e


class QueryIndexedContent(WebScraperBaseTool):
    """Tool for querying previously indexed web content.

    This tool searches through content that was previously scraped and indexed
    using the scrape_and_index tool to answer questions or find relevant information.
    """

    name: str = "web_scraper_query_indexed_content"
    description: str = (
        "Query previously indexed web content to find relevant information."
    )
    args_schema: ArgsSchema | None = QueryIndexInput

    async def _arun(
        self,
        query: str,
        max_results: int = 4,
        **kwargs,
    ) -> str:
        """Query the indexed content."""
        try:
            # Get agent context - throw error if not available
            # Configuration is always available in new runtime
            pass

            context = self.get_context()
            if not context or not context.agent_id:
                raise ToolException(
                    "Agent ID is required but not found in configuration"
                )

            agent_id = context.agent_id

            logger.info("[%s] Starting query operation: '%s'", agent_id, query)

            # Retrieve vector store
            vector_store_key = f"vector_store_{agent_id}"

            logger.info("[%s] Looking for vector store: %s", agent_id, vector_store_key)

            embedding_api_key = self.get_openai_api_key()
            vector_manager = VectorStoreManager(embedding_api_key)
            stored_data = await vector_manager.get_existing_vector_store(agent_id)

            if not stored_data:
                logger.warning("[%s] No vector store found", agent_id)
                return "No indexed content found. Please use the scrape_and_index tool first to scrape and index some web content before querying."

            if not stored_data or "faiss_files" not in stored_data:
                logger.warning("[%s] Invalid stored data structure", agent_id)
                return "No indexed content found. Please use the scrape_and_index tool first to scrape and index some web content before querying."

            # Create embeddings and decode vector store
            logger.info("[%s] Decoding vector store", agent_id)
            embeddings = vector_manager.create_embeddings()
            vector_store = vector_manager.decode_vector_store(
                stored_data["faiss_files"], embeddings
            )

            logger.info(
                "[%s] Vector store loaded, index count: %s",
                agent_id,
                vector_store.index.ntotal,
            )

            # Perform similarity search
            docs = vector_store.similarity_search(query, k=max_results)
            logger.info("[%s] Found %s similar documents", agent_id, len(docs))

            if not docs:
                logger.info("[%s] No relevant documents found for query", agent_id)
                return f"No relevant information found for your query: '{query}'. The indexed content may not contain information related to your search."

            # Format results
            results = []
            for i, doc in enumerate(docs, 1):
                content = doc.page_content.strip()
                source = doc.metadata.get("source", "Unknown")
                results.append(f"**Source {i}:** {source}\n{content}")

            response = "\n\n".join(results)
            logger.info(
                f"[{agent_id}] Query completed successfully, returning {len(response)} chars"
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
                f"[{agent_id}] Error in QueryIndexedContent: {e}", exc_info=True
            )
            raise type(e)(f"[agent:{agent_id}]: {e}") from e
