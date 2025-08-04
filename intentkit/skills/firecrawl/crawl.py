import asyncio
import logging
from typing import List, Optional, Type

import httpx
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from intentkit.skills.firecrawl.base import FirecrawlBaseTool

logger = logging.getLogger(__name__)


class FirecrawlCrawlInput(BaseModel):
    """Input for Firecrawl crawl tool."""

    url: str = Field(
        description="The base URL to crawl. All accessible subpages will be crawled."
    )
    limit: int = Field(
        description="Maximum number of pages to crawl", default=10, ge=1, le=1000
    )
    formats: List[str] = Field(
        description="Output formats to include in the response. Options: 'markdown', 'html', 'rawHtml', 'screenshot', 'links', 'json'",
        default=["markdown"],
    )
    include_paths: Optional[List[str]] = Field(
        description="Regex patterns to include in the crawl (e.g., ['^/blog/.*$'])",
        default=None,
    )
    exclude_paths: Optional[List[str]] = Field(
        description="Regex patterns to exclude from the crawl (e.g., ['^/admin/.*$'])",
        default=None,
    )
    max_depth: Optional[int] = Field(
        description="Maximum depth to crawl from the base URL",
        default=None,
        ge=1,
        le=10,
    )
    allow_backward_links: bool = Field(
        description="Allow crawling parent and sibling URLs, not just child paths",
        default=False,
    )
    allow_external_links: bool = Field(
        description="Allow crawling external domains (use with caution)", default=False
    )
    allow_subdomains: bool = Field(
        description="Allow crawling subdomains of the main domain", default=False
    )
    only_main_content: bool = Field(
        description="Whether to extract only the main content (excluding headers, footers, navigation, etc.)",
        default=True,
    )
    index_content: bool = Field(
        description="Whether to index the crawled content for later querying (default: True)",
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


class FirecrawlCrawl(FirecrawlBaseTool):
    """Tool for crawling entire websites using Firecrawl.

    This tool uses Firecrawl's API to crawl websites and extract content from multiple pages.
    It can handle JavaScript-rendered content, follow links, and extract structured data
    from entire websites.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "firecrawl_crawl"
    description: str = (
        "Crawl an entire website and extract content from multiple pages. "
        "This tool can follow links, handle JavaScript-rendered content, and extract "
        "structured data from all accessible pages on a website. "
        "Optionally indexes all crawled content for later querying using the firecrawl_query_indexed_content tool. "
        "Use this when you need to gather comprehensive information from a website."
    )
    args_schema: Type[BaseModel] = FirecrawlCrawlInput

    async def _arun(
        self,
        url: str,
        limit: int = 10,
        formats: List[str] = None,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
        allow_backward_links: bool = False,
        allow_external_links: bool = False,
        allow_subdomains: bool = False,
        only_main_content: bool = True,
        index_content: bool = True,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        **kwargs,
    ) -> str:
        """Implementation of the Firecrawl crawl tool.

        Args:
            url: The base URL to crawl.
            limit: Maximum number of pages to crawl.
            formats: Output formats to include in the response.
            include_paths: Regex patterns to include in the crawl.
            exclude_paths: Regex patterns to exclude from the crawl.
            max_depth: Maximum depth to crawl from the base URL.
            allow_backward_links: Allow crawling parent and sibling URLs.
            allow_external_links: Allow crawling external domains.
            allow_subdomains: Allow crawling subdomains.
            only_main_content: Whether to extract only main content.
            config: The configuration for the tool call.

        Returns:
            str: Formatted crawled content from all pages.
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        logger.debug(f"firecrawl_crawl: Running crawl with context {context}")

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
            "limit": min(limit, 1000),  # Cap at 1000 for safety
            "scrapeOptions": {"formats": formats, "onlyMainContent": only_main_content},
        }

        if include_paths:
            payload["includePaths"] = include_paths
        if exclude_paths:
            payload["excludePaths"] = exclude_paths
        if max_depth:
            payload["maxDepth"] = max_depth
        if allow_backward_links:
            payload["allowBackwardLinks"] = allow_backward_links
        if allow_external_links:
            payload["allowExternalLinks"] = allow_external_links
        if allow_subdomains:
            payload["allowSubdomains"] = allow_subdomains

        # Call Firecrawl crawl API
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Start the crawl
                response = await client.post(
                    "https://api.firecrawl.dev/v1/crawl",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"firecrawl_crawl: Error from Firecrawl API: {response.status_code} - {response.text}"
                    )
                    return f"Error starting crawl: {response.status_code} - {response.text}"

                crawl_data = response.json()

                if not crawl_data.get("success"):
                    error_msg = crawl_data.get("error", "Unknown error occurred")
                    return f"Error starting crawl: {error_msg}"

                crawl_id = crawl_data.get("id")
                if not crawl_id:
                    return "Error: No crawl ID returned from Firecrawl API"

                # Poll for crawl completion
                max_polls = 60  # Maximum 5 minutes of polling (60 * 5 seconds)
                poll_count = 0

                while poll_count < max_polls:
                    # Check crawl status
                    status_response = await client.get(
                        f"https://api.firecrawl.dev/v1/crawl/{crawl_id}",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )

                    if status_response.status_code != 200:
                        logger.error(
                            f"firecrawl_crawl: Error checking crawl status: {status_response.status_code} - {status_response.text}"
                        )
                        return f"Error checking crawl status: {status_response.status_code} - {status_response.text}"

                    status_data = status_response.json()
                    status = status_data.get("status")

                    if status == "completed":
                        # Crawl completed successfully
                        pages_data = status_data.get("data", [])
                        total_pages = status_data.get("total", 0)
                        completed_pages = status_data.get("completed", 0)

                        # Format the results
                        formatted_result = f"Successfully crawled: {url}\n"
                        formatted_result += f"Total pages found: {total_pages}\n"
                        formatted_result += f"Pages completed: {completed_pages}\n\n"

                        # Process each page
                        for i, page_data in enumerate(
                            pages_data[:10], 1
                        ):  # Limit to first 10 pages for output
                            page_url = page_data.get("metadata", {}).get(
                                "sourceURL", "Unknown URL"
                            )
                            formatted_result += f"## Page {i}: {page_url}\n"

                            if "markdown" in formats and page_data.get("markdown"):
                                content = page_data["markdown"][
                                    :500
                                ]  # Limit content length
                                formatted_result += f"{content}"
                                if len(page_data["markdown"]) > 500:
                                    formatted_result += "... (content truncated)"
                                formatted_result += "\n\n"

                            # Add page metadata
                            metadata = page_data.get("metadata", {})
                            if metadata.get("title"):
                                formatted_result += f"Title: {metadata['title']}\n"
                            if metadata.get("description"):
                                formatted_result += (
                                    f"Description: {metadata['description']}\n"
                                )
                            formatted_result += "\n"

                        if len(pages_data) > 10:
                            formatted_result += (
                                f"... and {len(pages_data) - 10} more pages\n"
                            )

                        # Index content if requested
                        if index_content and pages_data:
                            try:
                                # Import indexing utilities from firecrawl utils
                                from intentkit.skills.firecrawl.utils import (
                                    FirecrawlMetadataManager,
                                    index_documents,
                                )

                                # Create documents from crawled content
                                documents = []
                                for page_data in pages_data:
                                    if page_data.get("markdown"):
                                        metadata = page_data.get("metadata", {})
                                        document = Document(
                                            page_content=page_data["markdown"],
                                            metadata={
                                                "source": metadata.get(
                                                    "sourceURL", "Unknown URL"
                                                ),
                                                "title": metadata.get("title", ""),
                                                "description": metadata.get(
                                                    "description", ""
                                                ),
                                                "language": metadata.get(
                                                    "language", ""
                                                ),
                                                "source_type": "firecrawl_crawl",
                                                "indexed_at": str(context.agent_id),
                                            },
                                        )
                                        documents.append(document)

                                # Get agent ID for indexing
                                agent_id = context.agent_id
                                if agent_id and documents:
                                    # Index all documents
                                    total_chunks, was_merged = await index_documents(
                                        documents,
                                        agent_id,
                                        self.skill_store,
                                        chunk_size,
                                        chunk_overlap,
                                    )

                                    # Update metadata
                                    metadata_manager = FirecrawlMetadataManager(
                                        self.skill_store
                                    )
                                    urls = [doc.metadata["source"] for doc in documents]
                                    new_metadata = metadata_manager.create_url_metadata(
                                        urls, documents, "firecrawl_crawl"
                                    )
                                    await metadata_manager.update_metadata(
                                        agent_id, new_metadata
                                    )

                                    formatted_result += "\n## Content Indexing\n"
                                    formatted_result += "Successfully indexed crawled content into vector store:\n"
                                    formatted_result += (
                                        f"- Pages indexed: {len(documents)}\n"
                                    )
                                    formatted_result += (
                                        f"- Total chunks created: {total_chunks}\n"
                                    )
                                    formatted_result += f"- Chunk size: {chunk_size}\n"
                                    formatted_result += (
                                        f"- Chunk overlap: {chunk_overlap}\n"
                                    )
                                    formatted_result += f"- Content merged with existing: {'Yes' if was_merged else 'No'}\n"
                                    formatted_result += "Use the 'firecrawl_query_indexed_content' skill to search this content.\n"

                                    logger.info(
                                        f"firecrawl_crawl: Successfully indexed {len(documents)} pages with {total_chunks} total chunks"
                                    )
                                else:
                                    formatted_result += "\n## Content Indexing\n"
                                    formatted_result += "Warning: Could not index content - agent ID not available or no content to index.\n"

                            except Exception as index_error:
                                logger.error(
                                    f"firecrawl_crawl: Error indexing content: {index_error}"
                                )
                                formatted_result += "\n## Content Indexing\n"
                                formatted_result += f"Warning: Failed to index content for later querying: {str(index_error)}\n"

                        return formatted_result.strip()

                    elif status == "failed":
                        error_msg = status_data.get("error", "Crawl failed")
                        return f"Crawl failed: {error_msg}"

                    elif status in ["scraping", "active"]:
                        # Still in progress, wait and poll again
                        completed = status_data.get("completed", 0)
                        total = status_data.get("total", 0)
                        logger.debug(
                            f"firecrawl_crawl: Crawl in progress: {completed}/{total} pages"
                        )

                        # Wait 5 seconds before next poll
                        await asyncio.sleep(5)
                        poll_count += 1

                    else:
                        # Unknown status
                        logger.warning(
                            f"firecrawl_crawl: Unknown crawl status: {status}"
                        )
                        await asyncio.sleep(5)
                        poll_count += 1

                # If we've exceeded max polls, return partial results
                return f"Crawl timeout: The crawl of {url} is taking longer than expected. Please try again later or reduce the crawl limit."

        except httpx.TimeoutException:
            logger.error(f"firecrawl_crawl: Timeout crawling URL: {url}")
            return (
                f"Timeout error: The request to crawl {url} took too long to complete."
            )
        except Exception as e:
            logger.error(f"firecrawl_crawl: Error crawling URL: {e}", exc_info=True)
            return f"An error occurred while crawling the URL: {str(e)}"
