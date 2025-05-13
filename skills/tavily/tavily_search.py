import logging
from typing import Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.tavily.base import TavilyBaseTool

logger = logging.getLogger(__name__)


class TavilySearchInput(BaseModel):
    """Input for Tavily search tool."""

    query: str = Field(
        description="The search query to look up on the web.",
    )
    max_results: int = Field(
        description="Maximum number of search results to return (1-10).",
        default=5,
        ge=1,
        le=10,
    )
    include_images: bool = Field(
        description="Whether to include image URLs in the results.",
        default=False,
    )
    include_raw_content: bool = Field(
        description="Whether to include raw HTML content in the results.",
        default=False,
    )


class TavilySearch(TavilyBaseTool):
    """Tool for searching the web using Tavily.

    This tool uses Tavily's search API to search the web and return relevant results.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "tavily_search"
    description: str = (
        "Search the web for current information on a topic. Use this tool when you need to find"
        " up-to-date information, facts, news, or any content available online.\n"
        "You must call this tool whenever the user asks for information that may not be in your training data,"
        " requires current data, or when you're unsure about facts."
    )
    args_schema: Type[BaseModel] = TavilySearchInput

    async def _arun(
        self,
        query: str,
        max_results: int = 5,
        include_images: bool = False,
        include_raw_content: bool = False,
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Implementation of the Tavily search tool.

        Args:
            query: The search query to look up.
            max_results: Maximum number of search results to return (1-10).
            include_images: Whether to include image URLs in the results.
            include_raw_content: Whether to include raw HTML content in the results.
            config: The configuration for the tool call.

        Returns:
            str: Formatted search results with titles, snippets, and URLs.
        """
        context = self.context_from_config(config)
        logger.debug(f"tavily.py: Running web search with context {context}")

        if context.config.get("api_key_provider") == "agent_owner":
            if context.config.get("rate_limit_number") and context.config.get(
                "rate_limit_minutes"
            ):
                await self.user_rate_limit_by_category(
                    context.user_id,
                    context.config["rate_limit_number"],
                    context.config["rate_limit_minutes"],
                )

        # Get the API key from the agent's configuration
        api_key = self.get_api_key(context)
        if not api_key:
            return "Error: No Tavily API key provided in the configuration."

        # Limit max_results to a reasonable range
        max_results = max(1, min(max_results, 10))

        # Call Tavily search API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_images": include_images,
                        "include_raw_content": include_raw_content,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"tavily.py: Error from Tavily API: {response.status_code} - {response.text}"
                    )
                    return f"Error searching the web: {response.status_code} - {response.text}"

                data = response.json()
                results = data.get("results", [])

                if not results:
                    return f"No results found for query: '{query}'"

                # Format the results
                formatted_results = f"Web search results for: '{query}'\n\n"

                for i, result in enumerate(results, 1):
                    title = result.get("title", "No title")
                    content = result.get("content", "No content")
                    url = result.get("url", "No URL")

                    formatted_results += f"{i}. {title}\n"
                    formatted_results += f"{content}\n"
                    formatted_results += f"Source: {url}\n\n"

                return formatted_results.strip()

        except Exception as e:
            logger.error(f"tavily.py: Error searching web: {e}", exc_info=True)
            return "An error occurred while searching the web. Please try again later."
