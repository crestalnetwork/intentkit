import logging
from typing import List, Optional, Type

import httpx
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from intentkit.skills.firecrawl.base import FirecrawlBaseTool

logger = logging.getLogger(__name__)


class FirecrawlScrapeInput(BaseModel):
    """Input for Firecrawl scrape tool."""

    url: str = Field(
        description="The URL to scrape. Must be a valid HTTP or HTTPS URL."
    )
    formats: List[str] = Field(
        description="Output formats to include in the response. Options: 'markdown', 'html', 'rawHtml', 'screenshot', 'links', 'json'",
        default=["markdown"],
    )
    only_main_content: bool = Field(
        description="Whether to extract only the main content (excluding headers, footers, navigation, etc.)",
        default=True,
    )
    include_tags: Optional[List[str]] = Field(
        description="HTML tags, classes, or IDs to include in the response (e.g., ['h1', 'p', '.main-content'])",
        default=None,
    )
    exclude_tags: Optional[List[str]] = Field(
        description="HTML tags, classes, or IDs to exclude from the response (e.g., ['#ad', '#footer'])",
        default=None,
    )
    wait_for: int = Field(
        description="Wait time in milliseconds before scraping (use only as last resort)",
        default=0,
        ge=0,
    )
    timeout: int = Field(
        description="Maximum timeout in milliseconds for the scraping operation",
        default=30000,
        ge=1000,
        le=120000,
    )
    index_content: bool = Field(
        description="Whether to index the scraped content for later querying (default: True)",
        default=True,
    )
    chunk_size: int = Field(
        description="Size of text chunks for indexing (default: 1000)",
        default=1000,
        ge=100,
        le=4000,
    )
    chunk_overlap: int = Field(
        description="Overlap between chunks (default: 200)",
        default=200,
        ge=0,
        le=1000,
    )


class FirecrawlScrape(FirecrawlBaseTool):
    """Tool for scraping web pages using Firecrawl with REPLACE behavior.

    This tool uses Firecrawl's API to scrape web pages and REPLACES any existing
    indexed content for the same URL instead of appending to it. This prevents
    duplicate content when re-scraping the same page.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "firecrawl_scrape"
    description: str = (
        "Scrape a single web page and REPLACE any existing indexed content for that URL. "
        "Unlike regular scrape, this tool removes old content before adding new content, preventing duplicates. "
        "This tool can handle JavaScript-rendered content, PDFs, and dynamic websites. "
        "Use this when you want to refresh/update content from a URL that was previously scraped."
    )
    args_schema: Type[BaseModel] = FirecrawlScrapeInput

    async def _arun(
        self,
        url: str,
        formats: List[str] = None,
        only_main_content: bool = True,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        wait_for: int = 0,
        timeout: int = 30000,
        index_content: bool = True,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        **kwargs,
    ) -> str:
        """Implementation of the Firecrawl scrape tool.

        Args:
            url: The URL to scrape.
            formats: Output formats to include in the response.
            only_main_content: Whether to extract only main content.
            include_tags: HTML tags/classes/IDs to include.
            exclude_tags: HTML tags/classes/IDs to exclude.
            wait_for: Wait time in milliseconds before scraping.
            timeout: Maximum timeout in milliseconds.
            index_content: Whether to index the content for later querying.
            chunk_size: Size of text chunks for indexing.
            chunk_overlap: Overlap between chunks.
            config: The configuration for the tool call.

        Returns:
            str: Formatted scraped content based on the requested formats.
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        logger.debug(f"firecrawl_scrape: Running scrape with context {context}")

        if skill_config.get("api_key_provider") == "agent_owner":
            if skill_config.get("rate_limit_number") and skill_config.get(
                "rate_limit_minutes"
            ):
                await self.user_rate_limit_by_category(
                    context.user_id,
                    skill_config["rate_limit_number"],
                    skill_config["rate_limit_minutes"],
                )

        # Get the API key from the agent's configuration
        api_key = self.get_api_key()
        if not api_key:
            return "Error: No Firecrawl API key provided in the configuration."

        # Validate and set defaults
        if formats is None:
            formats = ["markdown"]

        # Validate formats
        valid_formats = ["markdown", "html", "rawHtml", "screenshot", "links", "json"]
        formats = [f for f in formats if f in valid_formats]
        if not formats:
            formats = ["markdown"]

        # Prepare the request payload
        payload = {
            "url": url,
            "formats": formats,
            "onlyMainContent": only_main_content,
            "timeout": timeout,
        }

        if include_tags:
            payload["includeTags"] = include_tags
        if exclude_tags:
            payload["excludeTags"] = exclude_tags
        if wait_for > 0:
            payload["waitFor"] = wait_for

        # Call Firecrawl scrape API
        try:
            async with httpx.AsyncClient(timeout=timeout / 1000 + 10) as client:
                response = await client.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"firecrawl_scrape: Error from Firecrawl API: {response.status_code} - {response.text}"
                    )
                    return (
                        f"Error scraping URL: {response.status_code} - {response.text}"
                    )

                data = response.json()

                if not data.get("success"):
                    error_msg = data.get("error", "Unknown error occurred")
                    return f"Error scraping URL: {error_msg}"

                result_data = data.get("data", {})

                # Format the results based on requested formats
                formatted_result = f"Successfully scraped (REPLACE mode): {url}\n\n"

                if "markdown" in formats and result_data.get("markdown"):
                    formatted_result += "## Markdown Content\n"
                    formatted_result += result_data["markdown"][:2000]  # Limit length
                    if len(result_data["markdown"]) > 2000:
                        formatted_result += "... (content truncated)"
                    formatted_result += "\n\n"

                if "html" in formats and result_data.get("html"):
                    formatted_result += "## HTML Content\n"
                    formatted_result += f"HTML content available ({len(result_data['html'])} characters)\n\n"

                if "links" in formats and result_data.get("links"):
                    formatted_result += "## Extracted Links\n"
                    links = result_data["links"][:10]  # Limit to first 10 links
                    for link in links:
                        formatted_result += f"- {link}\n"
                    if len(result_data["links"]) > 10:
                        formatted_result += (
                            f"... and {len(result_data['links']) - 10} more links\n"
                        )
                    formatted_result += "\n"

                if "json" in formats and result_data.get("json"):
                    formatted_result += "## Structured Data (JSON)\n"
                    formatted_result += str(result_data["json"])[:1000]  # Limit length
                    if len(str(result_data["json"])) > 1000:
                        formatted_result += "... (data truncated)"
                    formatted_result += "\n\n"

                if "screenshot" in formats and result_data.get("screenshot"):
                    formatted_result += "## Screenshot\n"
                    formatted_result += (
                        f"Screenshot available at: {result_data['screenshot']}\n\n"
                    )

                # Add metadata information
                metadata = result_data.get("metadata", {})
                if metadata:
                    formatted_result += "## Page Metadata\n"
                    if metadata.get("title"):
                        formatted_result += f"Title: {metadata['title']}\n"
                    if metadata.get("description"):
                        formatted_result += f"Description: {metadata['description']}\n"
                    if metadata.get("language"):
                        formatted_result += f"Language: {metadata['language']}\n"
                    formatted_result += "\n"

                # Index content if requested - REPLACE MODE
                if index_content and result_data.get("markdown"):
                    try:
                        # Import indexing utilities
                        from langchain_community.vectorstores import FAISS

                        from intentkit.skills.firecrawl.utils import (
                            FirecrawlDocumentProcessor,
                            FirecrawlMetadataManager,
                            FirecrawlVectorStoreManager,
                        )

                        # Create document from scraped content
                        document = Document(
                            page_content=result_data["markdown"],
                            metadata={
                                "source": url,
                                "title": metadata.get("title", ""),
                                "description": metadata.get("description", ""),
                                "language": metadata.get("language", ""),
                                "source_type": "firecrawl_scrape",
                                "indexed_at": str(context.agent_id),
                            },
                        )

                        # Get agent ID for indexing
                        agent_id = context.agent_id
                        if agent_id:
                            # Initialize managers
                            vs_manager = FirecrawlVectorStoreManager(self.skill_store)
                            metadata_manager = FirecrawlMetadataManager(
                                self.skill_store
                            )

                            # Load existing vector store
                            existing_vector_store = await vs_manager.load_vector_store(
                                agent_id
                            )

                            # Split the new document into chunks
                            split_docs = FirecrawlDocumentProcessor.split_documents(
                                [document], chunk_size, chunk_overlap
                            )

                            # Create embeddings
                            embeddings = vs_manager.create_embeddings()

                            if existing_vector_store:
                                # Get all existing documents and filter out those from the same URL
                                try:
                                    # Try to access documents directly if available
                                    if hasattr(
                                        existing_vector_store, "docstore"
                                    ) and hasattr(
                                        existing_vector_store.docstore, "_dict"
                                    ):
                                        # Access FAISS documents directly
                                        all_docs = list(
                                            existing_vector_store.docstore._dict.values()
                                        )
                                    else:
                                        # Fallback: use a reasonable k value for similarity search
                                        # Use a dummy query to retrieve documents
                                        all_docs = existing_vector_store.similarity_search(
                                            "dummy",  # Use a dummy query instead of empty string
                                            k=1000,  # Use reasonable upper bound
                                        )

                                    # Filter out documents from the same URL
                                    preserved_docs = [
                                        doc
                                        for doc in all_docs
                                        if doc.metadata.get("source") != url
                                    ]

                                    logger.info(
                                        f"firecrawl_scrape: Preserving {len(preserved_docs)} docs from other URLs, "
                                        f"replacing content from {url}"
                                    )

                                    # Create new vector store with preserved docs + new docs
                                    if preserved_docs:
                                        # Combine preserved and new documents
                                        all_documents = preserved_docs + split_docs
                                        new_vector_store = FAISS.from_documents(
                                            all_documents, embeddings
                                        )
                                        formatted_result += "\n## Content Replacement\n"
                                        formatted_result += f"Replaced existing content for URL: {url}\n"
                                        num_preserved_urls = len(
                                            set(
                                                doc.metadata.get("source", "")
                                                for doc in preserved_docs
                                            )
                                        )
                                        formatted_result += f"Preserved content from {num_preserved_urls} other URLs\n"
                                    else:
                                        # No other documents to preserve, just create from new docs
                                        new_vector_store = FAISS.from_documents(
                                            split_docs, embeddings
                                        )
                                        formatted_result += "\n## Content Replacement\n"
                                        formatted_result += f"Created new index with content from: {url}\n"
                                except Exception as e:
                                    logger.warning(
                                        f"Could not preserve other URLs, creating fresh index: {e}"
                                    )
                                    # Fallback: create new store with just the new documents
                                    new_vector_store = FAISS.from_documents(
                                        split_docs, embeddings
                                    )
                                    formatted_result += "\n## Content Replacement\n"
                                    formatted_result += f"Created fresh index with content from: {url}\n"
                            else:
                                # No existing store, create new one
                                new_vector_store = FAISS.from_documents(
                                    split_docs, embeddings
                                )
                                formatted_result += "\n## Content Indexing\n"
                                formatted_result += (
                                    f"Created new index with content from: {url}\n"
                                )

                            # Save the new vector store
                            await vs_manager.save_vector_store(
                                agent_id, new_vector_store, chunk_size, chunk_overlap
                            )

                            # Update metadata to track all URLs
                            # Get existing metadata to preserve other URLs
                            metadata_key = f"indexed_urls_{agent_id}"
                            existing_metadata = (
                                await self.skill_store.get_agent_skill_data(
                                    agent_id, "firecrawl", metadata_key
                                )
                            )

                            if existing_metadata and existing_metadata.get("urls"):
                                # Remove the current URL and add it back (to update timestamp)
                                existing_urls = [
                                    u for u in existing_metadata["urls"] if u != url
                                ]
                                existing_urls.append(url)
                                updated_metadata = {
                                    "urls": existing_urls,
                                    "document_count": len(existing_urls),
                                    "source_type": "firecrawl_mixed",
                                    "indexed_at": str(len(existing_urls)),
                                }
                            else:
                                # Create new metadata
                                updated_metadata = metadata_manager.create_url_metadata(
                                    [url], [document], "firecrawl_scrape"
                                )

                            await metadata_manager.update_metadata(
                                agent_id, updated_metadata
                            )

                            formatted_result += "\n## Content Indexing (REPLACE MODE)\n"
                            formatted_result += "Successfully REPLACED indexed content in vector store:\n"
                            formatted_result += f"- Chunks created: {len(split_docs)}\n"
                            formatted_result += f"- Chunk size: {chunk_size}\n"
                            formatted_result += f"- Chunk overlap: {chunk_overlap}\n"
                            formatted_result += (
                                "- Previous content for this URL: REPLACED\n"
                            )
                            formatted_result += "Use the 'firecrawl_query_indexed_content' skill to search this content.\n"

                            logger.info(
                                f"firecrawl_scrape: Successfully replaced content for {url} with {len(split_docs)} chunks"
                            )
                        else:
                            formatted_result += "\n## Content Indexing\n"
                            formatted_result += "Warning: Could not index content - agent ID not available.\n"

                    except Exception as index_error:
                        logger.error(
                            f"firecrawl_scrape: Error indexing content: {index_error}"
                        )
                        formatted_result += "\n## Content Indexing\n"
                        formatted_result += f"Warning: Failed to index content for later querying: {str(index_error)}\n"

                return formatted_result.strip()

        except httpx.TimeoutException:
            logger.error(f"firecrawl_scrape: Timeout scraping URL: {url}")
            return (
                f"Timeout error: The request to scrape {url} took too long to complete."
            )
        except Exception as e:
            logger.error(f"firecrawl_scrape: Error scraping URL: {e}", exc_info=True)
            return f"An error occurred while scraping the URL: {str(e)}"
