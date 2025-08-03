import logging
from enum import Enum
from typing import Type

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.github.base import GitHubBaseTool

logger = logging.getLogger(__name__)


class SearchType(str, Enum):
    REPOSITORIES = "repositories"
    USERS = "users"
    CODE = "code"


class GitHubSearchInput(BaseModel):
    """Input for GitHub search tool."""

    query: str = Field(
        description="The search query to look up on GitHub.",
    )
    search_type: SearchType = Field(
        description="Type of GitHub search to perform (repositories, users, or code).",
        default=SearchType.REPOSITORIES,
    )
    max_results: int = Field(
        description="Maximum number of search results to return (1-30).",
        default=5,
        ge=1,
        le=30,
    )


class GitHubSearch(GitHubBaseTool):
    """Tool for searching GitHub.

    This tool uses GitHub's public REST API to search for repositories, users, and code.
    No authentication is required as it uses public endpoints.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "github_search"
    description: str = (
        "Search GitHub for repositories, users, or code. Use this tool when you need to find:\n"
        "- GitHub repositories by name, description, or topics\n"
        "- GitHub users by username or real name\n"
        "- Code snippets across GitHub repositories\n"
        "You must call this tool whenever the user asks about finding something on GitHub."
    )
    args_schema: Type[BaseModel] = GitHubSearchInput

    async def _arun(
        self,
        query: str,
        search_type: SearchType = SearchType.REPOSITORIES,
        max_results: int = 5,
        **kwargs,
    ) -> str:
        """Implementation of the GitHub search tool.

        Args:
            query: The search query to look up.
            search_type: Type of search to perform (repositories, users, or code).
            max_results: Maximum number of search results to return (1-30).
            config: The configuration for the tool call.

        Returns:
            str: Formatted search results based on the search type.
        """
        context = self.get_context()
        logger.debug(f"github_search.py: Running GitHub search with context {context}")

        # Limit max_results to a reasonable range
        max_results = max(1, min(max_results, 30))

        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        # Build the search URL based on search type
        base_url = "https://api.github.com/search"
        search_url = f"{base_url}/{search_type.value}"
        logger.debug(f"github_search.py: Searching GitHub at {search_url}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    search_url,
                    headers=headers,
                    params={"q": query, "per_page": max_results},
                )

                if response.status_code == 403:
                    rate_limit = response.headers.get(
                        "X-RateLimit-Remaining", "unknown"
                    )
                    reset_time = response.headers.get("X-RateLimit-Reset", "unknown")
                    logger.warning(
                        f"github_search.py: Rate limit reached. Remaining: {rate_limit}, Reset: {reset_time}"
                    )
                    return (
                        "GitHub API rate limit reached. Please try again in a few minutes. "
                        "The rate limit resets every hour for unauthenticated requests."
                    )
                elif response.status_code != 200:
                    logger.error(
                        f"github_search.py: Error from GitHub API: {response.status_code} - {response.text}"
                    )
                    return f"Error searching GitHub: {response.status_code} - {response.text}"

                data = response.json()
                items = data.get("items", [])

                if not items:
                    return f"No results found for query: '{query}'"

                # Format results based on search type
                formatted_results = (
                    f"GitHub search results for '{query}' ({search_type.value}):\n\n"
                )

                for i, item in enumerate(items, 1):
                    if search_type == SearchType.REPOSITORIES:
                        name = item.get("full_name", "No name")
                        description = item.get("description", "No description")
                        url = item.get("html_url", "No URL")
                        stars = item.get("stargazers_count", 0)
                        language = item.get("language", "Not specified")

                        formatted_results += f"{i}. {name}\n"
                        formatted_results += f"Description: {description}\n"
                        formatted_results += f"Language: {language} | Stars: {stars}\n"
                        formatted_results += f"URL: {url}\n\n"

                    elif search_type == SearchType.USERS:
                        login = item.get("login", "No username")
                        name = item.get("name", "No name")
                        bio = item.get("bio", "No bio")
                        url = item.get("html_url", "No URL")
                        followers = item.get("followers", 0)
                        public_repos = item.get("public_repos", 0)

                        formatted_results += f"{i}. {login}"
                        if name:
                            formatted_results += f" ({name})"
                        formatted_results += "\n"
                        if bio:
                            formatted_results += f"Bio: {bio}\n"
                        formatted_results += (
                            f"Followers: {followers} | Public Repos: {public_repos}\n"
                        )
                        formatted_results += f"URL: {url}\n\n"

                    elif search_type == SearchType.CODE:
                        repo = item.get("repository", {}).get(
                            "full_name", "No repository"
                        )
                        path = item.get("path", "No path")
                        url = item.get("html_url", "No URL")

                        formatted_results += f"{i}. Found in {repo}\n"
                        formatted_results += f"File: {path}\n"
                        formatted_results += f"URL: {url}\n\n"

                return formatted_results.strip()

        except httpx.TimeoutException:
            logger.error("github_search.py: Request timed out")
            return "The request to GitHub timed out. Please try again later."
        except Exception as e:
            logger.error(
                f"github_search.py: Error searching GitHub: {e}", exc_info=True
            )
            return "An error occurred while searching GitHub. Please try again later."
