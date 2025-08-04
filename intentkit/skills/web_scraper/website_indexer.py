import logging
from typing import List, Type
from urllib.parse import urljoin, urlparse

import httpx
import openai
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


class WebsiteIndexerInput(BaseModel):
    """Input for WebsiteIndexer tool."""

    base_url: str = Field(
        description="Base URL of the website to index (e.g., https://example.com). The tool will discover sitemaps and extract all URLs",
        min_length=1,
    )
    max_urls: int = Field(
        description="Maximum number of URLs to scrape from the sitemap (default: 50)",
        default=50,
        ge=1,
        le=200,
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
    include_patterns: List[str] = Field(
        description="URL patterns to include (e.g., ['/blog/', '/docs/']). If empty, all URLs are included",
        default=[],
    )
    exclude_patterns: List[str] = Field(
        description="URL patterns to exclude (e.g., ['/admin/', '/private/'])",
        default=[],
    )


class WebsiteIndexer(WebScraperBaseTool):
    """Tool for discovering and indexing entire websites using AI-powered sitemap analysis.

    This tool discovers sitemaps from robots.txt, extracts URLs from sitemap XML using GPT-4o-mini for
    robust parsing of various sitemap formats, and then delegates to the proven scrape_and_index tool
    for reliable content indexing.
    """

    name: str = "web_scraper_website_indexer"
    description: str = (
        "Index an entire website by discovering sitemaps and extracting URLs efficiently. "
        "This tool finds sitemaps from robots.txt, parses the XML content to extract URLs, "
        "and then uses the reliable scrape_and_index functionality for content indexing."
    )
    args_schema: Type[BaseModel] = WebsiteIndexerInput

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by ensuring it has a proper scheme."""
        if not url.startswith(("http://", "https://")):
            return f"https://{url}"
        return url

    async def _get_robots_txt(self, base_url: str) -> str:
        """Fetch robots.txt content."""
        robots_url = urljoin(base_url, "/robots.txt")

        # Import headers from utils
        from intentkit.skills.web_scraper.utils import DEFAULT_HEADERS, FALLBACK_HEADERS

        # Try with primary headers first
        async with httpx.AsyncClient(timeout=30, headers=DEFAULT_HEADERS) as client:
            try:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                logger.warning(
                    f"Primary headers failed for robots.txt from {robots_url}: {e}"
                )

        # Try with fallback headers
        async with httpx.AsyncClient(timeout=30, headers=FALLBACK_HEADERS) as client:
            try:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                logger.warning(f"Could not fetch robots.txt from {robots_url}: {e}")
        return ""

    def _extract_sitemaps_from_robots(
        self, robots_content: str, base_url: str
    ) -> List[str]:
        """Extract sitemap URLs from robots.txt content."""
        sitemaps = []

        for line in robots_content.split("\n"):
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                # Make relative URLs absolute
                if sitemap_url.startswith("/"):
                    sitemap_url = urljoin(base_url, sitemap_url)
                sitemaps.append(sitemap_url)

        return sitemaps

    def _get_common_sitemap_patterns(self, base_url: str) -> List[str]:
        """Generate common sitemap URL patterns."""
        return [
            urljoin(base_url, "/sitemap.xml"),
            urljoin(base_url, "/sitemap_index.xml"),
            urljoin(base_url, "/sitemaps/sitemap.xml"),
            urljoin(base_url, "/sitemap/sitemap.xml"),
            urljoin(base_url, "/wp-sitemap.xml"),  # WordPress
        ]

    async def _fetch_sitemap_content(self, sitemap_url: str) -> str:
        """Fetch sitemap XML content."""
        # Import headers from utils
        from intentkit.skills.web_scraper.utils import DEFAULT_HEADERS, FALLBACK_HEADERS

        # Try with primary headers first
        async with httpx.AsyncClient(timeout=30, headers=DEFAULT_HEADERS) as client:
            try:
                response = await client.get(sitemap_url)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                logger.warning(
                    f"Primary headers failed for sitemap from {sitemap_url}: {e}"
                )

        # Try with fallback headers
        async with httpx.AsyncClient(timeout=30, headers=FALLBACK_HEADERS) as client:
            try:
                response = await client.get(sitemap_url)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                logger.warning(f"Could not fetch sitemap from {sitemap_url}: {e}")
        return ""

    async def _get_all_sitemap_content(self, base_url: str) -> tuple[str, List[str]]:
        """Get all sitemap content for AI analysis."""
        all_content = []
        found_sitemaps = []
        processed_sitemaps = set()

        # First, try to get sitemaps from robots.txt
        robots_content = await self._get_robots_txt(base_url)
        sitemap_urls = self._extract_sitemaps_from_robots(robots_content, base_url)

        # If no sitemaps found in robots.txt, try common patterns
        if not sitemap_urls:
            sitemap_urls = self._get_common_sitemap_patterns(base_url)

        logger.info(f"Checking {len(sitemap_urls)} potential sitemap URLs...")

        # Process each sitemap URL
        sitemaps_to_process = sitemap_urls[:]

        while sitemaps_to_process:
            sitemap_url = sitemaps_to_process.pop(0)

            if sitemap_url in processed_sitemaps:
                continue

            processed_sitemaps.add(sitemap_url)

            xml_content = await self._fetch_sitemap_content(sitemap_url)
            if not xml_content:
                continue

            found_sitemaps.append(sitemap_url)
            all_content.append(f"<!-- Sitemap: {sitemap_url} -->\n{xml_content}\n")

            # Check if this contains references to other sitemaps (sitemap index)
            if "<sitemap>" in xml_content.lower() and "<loc>" in xml_content.lower():
                # This might be a sitemap index - we'll let AI handle parsing it
                pass

        combined_xml = "\n".join(all_content) if all_content else ""
        return combined_xml, found_sitemaps

    def _create_ai_extraction_prompt(
        self, sitemap_xml: str, include_patterns: List[str], exclude_patterns: List[str]
    ) -> str:
        """Create a prompt for AI to extract URLs from sitemap XML."""
        filter_instructions = ""
        if include_patterns:
            filter_instructions += f"\n- INCLUDE only URLs containing these patterns: {', '.join(include_patterns)}"
        if exclude_patterns:
            filter_instructions += f"\n- EXCLUDE URLs containing these patterns: {', '.join(exclude_patterns)}"

        return f"""Analyze this sitemap XML and extract all valid webpage URLs.

SITEMAP XML CONTENT:
{sitemap_xml}

INSTRUCTIONS:
- Extract only URLs from <loc> tags that point to actual web pages
- Handle both standard sitemap format and sitemap index format
- Ignore any URLs ending in .xml, .rss, .atom (these are feeds/sitemaps, not pages)
- Skip any sitemap index entries that point to other sitemaps  
- Handle text-based sitemaps (simple URL lists)
- Return only unique, valid HTTP/HTTPS URLs
- Format as a simple list, one URL per line{filter_instructions}

Extract the URLs now:"""

    def _parse_ai_response(self, ai_response: str) -> List[str]:
        """Parse AI response to extract clean URLs."""
        urls = []

        for line in ai_response.strip().split("\n"):
            line = line.strip()
            # Remove any markdown formatting, bullets, numbering
            line = line.lstrip("- •*123456789. ")

            # Check if it looks like a URL
            if line.startswith(("http://", "https://")):
                # Basic validation
                try:
                    parsed = urlparse(line)
                    if parsed.netloc and not line.endswith((".xml", ".rss", ".atom")):
                        urls.append(line)
                except Exception:
                    continue

        return list(set(urls))  # Remove duplicates

    async def _call_ai_model(self, prompt: str, context) -> str:
        """Call OpenAI GPT-4o-mini to extract URLs from sitemap content."""
        try:
            # Get OpenAI API key using the standard pattern
            from intentkit.skills.openai.base import OpenAIBaseTool

            temp_tool = OpenAIBaseTool(skill_store=self.skill_store)
            api_key = temp_tool.get_api_key()

            # Initialize OpenAI client
            client = openai.AsyncOpenAI(api_key=api_key)

            # Call the API
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at parsing XML sitemaps and extracting webpage URLs. Always return only clean, valid URLs, one per line.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise

    async def _arun(
        self,
        base_url: str,
        max_urls: int = 50,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None,
        **kwargs,
    ) -> str:
        """Discover website sitemaps, extract URLs with AI, and delegate to scrape_and_index."""
        try:
            # Normalize inputs
            base_url = self._normalize_url(base_url)
            include_patterns = include_patterns or []
            exclude_patterns = exclude_patterns or []

            # Validate base URL
            parsed_url = urlparse(base_url)
            if not parsed_url.netloc:
                return "Error: Invalid base URL provided. Please provide a valid URL (e.g., https://example.com)"

                # Get agent context - throw error if not available
                # TODO: Fix config reference
                raise ValueError("Configuration is required but not provided")

            context = self.get_context()
            if not context or not context.agent_id:
                raise ValueError("Agent ID is required but not found in configuration")

            agent_id = context.agent_id

            logger.info(f"[{agent_id}] Discovering sitemaps for {base_url}...")

            # Get all sitemap content
            sitemap_xml, found_sitemaps = await self._get_all_sitemap_content(base_url)

            if not sitemap_xml:
                logger.error(
                    f"[{agent_id}] No accessible sitemaps found for {base_url}"
                )
                return f"Error: No accessible sitemaps found for {base_url}. The website might not have sitemaps or they might be inaccessible."

            logger.info(
                f"[{agent_id}] Found {len(found_sitemaps)} sitemap(s). Extracting URLs with AI..."
            )

            try:
                # Use AI to extract URLs from sitemap
                prompt = self._create_ai_extraction_prompt(
                    sitemap_xml, include_patterns, exclude_patterns
                )
                ai_response = await self._call_ai_model(prompt, context)
                all_urls = self._parse_ai_response(ai_response)

                logger.info(
                    f"[{agent_id}] AI extracted {len(all_urls)} URLs from sitemap"
                )

            except Exception as e:
                logger.error(
                    f"[{agent_id}] AI extraction failed: {e}, falling back to regex"
                )
                # Fallback to simple regex if AI fails
                import re

                url_pattern = r"<loc>(https?://[^<]+)</loc>"
                all_urls = re.findall(url_pattern, sitemap_xml)

                # Basic filtering for fallback
                filtered_urls = []
                for url in all_urls:
                    # Skip XML files (sitemaps)
                    if url.endswith((".xml", ".rss", ".atom")):
                        continue

                    # Apply exclude patterns
                    if exclude_patterns and any(
                        pattern in url for pattern in exclude_patterns
                    ):
                        continue

                    # Apply include patterns
                    if include_patterns:
                        if any(pattern in url for pattern in include_patterns):
                            filtered_urls.append(url)
                    else:
                        filtered_urls.append(url)

                all_urls = filtered_urls
                logger.info(
                    f"[{agent_id}] Regex fallback extracted {len(all_urls)} URLs from sitemap"
                )

            # Remove duplicates and limit
            unique_urls = list(set(all_urls))[:max_urls]

            if not unique_urls:
                logger.error(
                    f"[{agent_id}] No valid URLs found in sitemaps after filtering"
                )
                return f"Error: No valid URLs found in sitemaps after filtering. Found sitemaps: {', '.join(found_sitemaps)}"

            logger.info(
                f"[{agent_id}] Extracted {len(unique_urls)} URLs from sitemaps. Scraping and indexing..."
            )

            # Use the utility function to scrape and index URLs directly
            total_chunks, was_merged, valid_urls = await scrape_and_index_urls(
                unique_urls, agent_id, self.skill_store, chunk_size, chunk_overlap
            )

            if total_chunks == 0:
                logger.error(
                    f"[{agent_id}] No content could be extracted from discovered URLs"
                )
                return f"Error: No content could be extracted from the discovered URLs. Found sitemaps: {', '.join(found_sitemaps)}"

            # Get current storage size for response
            vs_manager = VectorStoreManager(self.skill_store)
            current_size = await vs_manager.get_content_size(agent_id)
            size_limit_reached = len(valid_urls) < len(unique_urls)

            # Update metadata
            metadata_manager = MetadataManager(self.skill_store)
            new_metadata = metadata_manager.create_url_metadata(
                valid_urls, [], "website_indexer"
            )
            await metadata_manager.update_metadata(agent_id, new_metadata)

            logger.info(f"[{agent_id}] Website indexing completed successfully")

            # Format the indexing result
            result = ResponseFormatter.format_indexing_response(
                "scraped and indexed",
                valid_urls,
                total_chunks,
                chunk_size,
                chunk_overlap,
                was_merged,
                current_size_bytes=current_size,
                size_limit_reached=size_limit_reached,
                total_requested_urls=len(unique_urls),
            )

            # Enhance the response with sitemap discovery info
            enhanced_result = (
                f"WEBSITE INDEXING COMPLETE\n"
                f"Base URL: {base_url}\n"
                f"Sitemaps discovered: {len(found_sitemaps)}\n"
                f"URLs extracted: {len(unique_urls)}\n"
                f"URLs successfully indexed: {len(valid_urls)}\n"
                f"Include patterns: {', '.join(include_patterns) if include_patterns else 'None (all URLs)'}\n"
                f"Exclude patterns: {', '.join(exclude_patterns) if exclude_patterns else 'None'}\n\n"
                f"DISCOVERED SITEMAPS:\n"
                f"{chr(10).join(['- ' + sitemap for sitemap in found_sitemaps])}\n\n"
                f"INDEXING RESULTS:\n{result}"
            )

            return enhanced_result

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

            logger.error(f"[{agent_id}] Error in WebsiteIndexer: {e}", exc_info=True)
            raise type(e)(f"[agent:{agent_id}]: {e}") from e
