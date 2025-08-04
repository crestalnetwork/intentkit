import logging
from typing import Type

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.tavily.base import TavilyBaseTool

logger = logging.getLogger(__name__)


class TavilyExtractInput(BaseModel):
    """Input for Tavily extract tool."""

    urls: str = Field(
        description="The URL to extract content from.",
    )
    include_images: bool = Field(
        description="Include a list of images extracted from the URLs in the response.",
        default=False,
    )
    extract_depth: str = Field(
        description="The depth of the extraction process. 'advanced' retrieves more data including tables and embedded content with higher success but may increase latency. 'basic' costs 1 credit per 5 successful URL extractions, while 'advanced' costs 2 credits per 5 successful URL extractions.",
        default="basic",
    )


class TavilyExtract(TavilyBaseTool):
    """Tool for extracting web page content using Tavily.

    This tool uses Tavily's extract API to retrieve content from specified URLs.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "tavily_extract"
    description: str = (
        "Extract web page content from a specified URL using Tavily Extract. "
        "This tool is useful when you need to get the full text content from a webpage. "
        "You must call this tool whenever the user asks to extract or scrape content from a specific URL."
    )
    args_schema: Type[BaseModel] = TavilyExtractInput

    async def _arun(
        self,
        urls: str,
        include_images: bool = False,
        extract_depth: str = "basic",
        **kwargs,
    ) -> str:
        """Implementation of the Tavily extract tool.

        Args:
            urls: The URL to extract content from.
            include_images: Whether to include image URLs in the results.
            extract_depth: The depth of the extraction process ('basic' or 'advanced').
            config: The configuration for the tool call.

        Returns:
            str: Formatted extraction results with content from the URL.
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        logger.debug(
            f"tavily_extract.py: Running web extraction with context {context}"
        )

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
            return "Error: No Tavily API key provided in the configuration."

        # Validate extract_depth
        if extract_depth not in ["basic", "advanced"]:
            extract_depth = "basic"
            logger.warning(
                "tavily_extract.py: Invalid extract_depth provided. Using default 'basic'."
            )

        # Call Tavily extract API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/extract",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "urls": urls,
                        "include_images": include_images,
                        "extract_depth": extract_depth,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"tavily_extract.py: Error from Tavily API: {response.status_code} - {response.text}"
                    )
                    return f"Error extracting web page content: {response.status_code} - {response.text}"

                data = response.json()
                results = data.get("results", [])

                if not results:
                    return f"No content could be extracted from URL: '{urls}'"

                # Format the results
                formatted_results = f"Web page content extracted from: '{urls}'\n\n"

                for i, result in enumerate(results, 1):
                    url = result.get("url", "No URL")
                    raw_content = result.get("raw_content", "No content available")

                    # Truncate the content if it's too long (over 2000 characters)
                    if len(raw_content) > 2000:
                        raw_content = raw_content[:2000] + "...[content truncated]"

                    formatted_results += f"{i}. Content from {url}:\n\n"
                    formatted_results += f"{raw_content}\n\n"

                    # Add images if available and requested
                    if include_images and "images" in result and result["images"]:
                        formatted_results += "Images:\n"
                        for j, image_url in enumerate(result["images"], 1):
                            formatted_results += f"  {j}. {image_url}\n"
                        formatted_results += "\n"

                return formatted_results.strip()

        except Exception as e:
            logger.error(
                f"tavily_extract.py: Error extracting web page content: {e}",
                exc_info=True,
            )
            return "An error occurred while extracting web page content. Please try again later."
