import logging
from typing import List, Type

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

    urls: List[str] = Field(
        description="List of URLs to scrape and index. Each URL should be a valid web address starting with http:// or https://",
        min_items=1,
        max_items=25,
    )
    chunk_size: int = Field(
        description="Size of text chunks for indexing (default: 1000)",
        default=DEFAULT_CHUNK_SIZE,
        ge=100,
        le=4000,
    )
    chunk_overlap: int = Field(
        description="Overlap between chunks (default: 200)",
        default=DEFAULT_CHUNK_OVERLAP,
        ge=0,
        le=1000,
    )


class QueryIndexInput(BaseModel):
    """Input for QueryIndex tool."""

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


class ScrapeAndIndex(WebScraperBaseTool):
    """Tool for scraping web content and indexing it into a searchable vector store.

    This tool can scrape multiple URLs, process the content into chunks,
    and store it in a vector database for later retrieval and question answering.
    """

    name: str = "web_scraper_scrape_and_index"
    description: str = (
        "Scrape content from one or more web URLs and index them into a vector store for later querying.\n"
        "Use this tool to collect and index web content that you want to reference later.\n"
        "The indexed content can then be queried using the query_indexed_content tool."
    )
    args_schema: Type[BaseModel] = ScrapeAndIndexInput

    async def _arun(
        self,
        urls: List[str],
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
                raise ValueError("Agent ID is required but not found in configuration")

            agent_id = context.agent_id

            logger.info(
                f"[{agent_id}] Starting scrape and index operation with {len(urls)} URLs"
            )

            # Use the utility function to scrape and index URLs
            total_chunks, was_merged, valid_urls = await scrape_and_index_urls(
                urls, agent_id, self.skill_store, chunk_size, chunk_overlap
            )

            logger.info(
                f"[{agent_id}] Scraping completed: {total_chunks} chunks indexed, merged: {was_merged}"
            )

            if not valid_urls:
                logger.error(f"[{agent_id}] No valid URLs provided")
                return "Error: No valid URLs provided. URLs must start with http:// or https://"

            if total_chunks == 0:
                logger.error(f"[{agent_id}] No content extracted from URLs")
                return "Error: No content could be extracted from the provided URLs."

            # Get current storage size for response
            vs_manager = VectorStoreManager(self.skill_store)
            current_size = await vs_manager.get_content_size(agent_id)
            size_limit_reached = len(valid_urls) < len(urls)

            # Update metadata
            metadata_manager = MetadataManager(self.skill_store)
            new_metadata = metadata_manager.create_url_metadata(
                valid_urls, [], "scrape_and_index"
            )
            await metadata_manager.update_metadata(agent_id, new_metadata)

            logger.info(f"[{agent_id}] Metadata updated successfully")

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
                f"[{agent_id}] Scrape and index operation completed successfully"
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

            logger.error(f"[{agent_id}] Error in ScrapeAndIndex: {e}", exc_info=True)
            raise type(e)(f"[agent:{agent_id}]: {e}") from e


class QueryIndexedContent(WebScraperBaseTool):
    """Tool for querying previously indexed web content.

    This tool searches through content that was previously scraped and indexed
    using the scrape_and_index tool to answer questions or find relevant information.
    """

    name: str = "web_scraper_query_indexed_content"
    description: str = (
        "Query previously indexed web content to find relevant information and answer questions.\n"
        "Use this tool to search through content that was previously scraped and indexed.\n"
        "This tool can help answer questions based on the indexed web content."
    )
    args_schema: Type[BaseModel] = QueryIndexInput

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
                raise ValueError("Agent ID is required but not found in configuration")

            agent_id = context.agent_id

            logger.info(f"[{agent_id}] Starting query operation: '{query}'")

            # Retrieve vector store
            vector_store_key = f"vector_store_{agent_id}"

            logger.info(f"[{agent_id}] Looking for vector store: {vector_store_key}")

            stored_data = await self.skill_store.get_agent_skill_data(
                agent_id, "web_scraper", vector_store_key
            )

            if not stored_data:
                logger.warning(f"[{agent_id}] No vector store found")
                return "No indexed content found. Please use the scrape_and_index tool first to scrape and index some web content before querying."

            if not stored_data or "faiss_files" not in stored_data:
                logger.warning(f"[{agent_id}] Invalid stored data structure")
                return "No indexed content found. Please use the scrape_and_index tool first to scrape and index some web content before querying."

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
