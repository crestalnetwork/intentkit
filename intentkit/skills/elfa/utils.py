"""Utility functions for Elfa skills."""

from typing import Any

import httpx
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from .base import base_url


class ElfaResponse(BaseModel):
    """Standard Elfa API v2 response format."""

    success: bool
    data: Any = None
    metadata: dict[str, Any] | None = None


async def make_elfa_request(
    endpoint: str,
    api_key: str,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
) -> ElfaResponse:
    """
    Make a standardized request to the Elfa API.

    Args:
        endpoint: API endpoint path (e.g., "aggregations/trending-tokens")
        api_key: Elfa API key
        params: Query parameters
        timeout: Request timeout in seconds

    Returns:
        ElfaResponse: Standardized response object

    Raises:
        ToolException: If there's an error with the API request
    """
    if not api_key:
        raise ValueError("Elfa API key not found")

    url = f"{base_url}/{endpoint}"
    headers = {
        "accept": "application/json",
        "x-elfa-api-key": api_key,
    }

    # Clean up params - remove None values
    if params:
        params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url, headers=headers, timeout=timeout, params=params
            )
            response.raise_for_status()
            json_dict = response.json()

            # Handle v2 response format
            if isinstance(json_dict, dict) and "success" in json_dict:
                return ElfaResponse(
                    success=json_dict["success"],
                    data=json_dict.get("data"),
                    metadata=json_dict.get("metadata", {}),
                )
            else:
                # Fallback for unexpected format
                return ElfaResponse(success=True, data=json_dict, metadata={})

        except httpx.RequestError as req_err:
            raise ToolException(f"Request error from Elfa API: {req_err}") from req_err
        except httpx.HTTPStatusError as http_err:
            raise ToolException(f"HTTP error from Elfa API: {http_err}") from http_err
        except Exception as e:
            raise ToolException(f"Error from Elfa API: {e}") from e


# Common Pydantic models for v2 API responses
class RepostBreakdown(BaseModel):
    """Repost breakdown data."""

    smart: int | None = None
    ct: int | None = None


class Account(BaseModel):
    """Account information."""

    username: str | None = None
    isVerified: bool | None = None


class MentionData(BaseModel):
    """Base mention data structure used across multiple endpoints."""

    tweetId: str | None = Field(None, description="Tweet ID")
    link: str | None = Field(None, description="Link to the tweet")
    likeCount: int | None = Field(None, description="Number of likes")
    repostCount: int | None = Field(None, description="Number of reposts")
    viewCount: int | None = Field(None, description="Number of views")
    quoteCount: int | None = Field(None, description="Number of quotes")
    replyCount: int | None = Field(None, description="Number of replies")
    bookmarkCount: int | None = Field(None, description="Number of bookmarks")
    mentionedAt: str | None = Field(None, description="When mentioned")
    type: str | None = Field(None, description="Post type")
    account: Account | None = Field(None, description="Account information")
    repostBreakdown: RepostBreakdown | None = Field(
        None, description="Repost breakdown"
    )


class SmartStatsData(BaseModel):
    """Smart stats data structure."""

    smartFollowingCount: int | None = Field(None, description="Smart following count")
    averageEngagement: float | None = Field(None, description="Average engagement")
    averageReach: float | None = Field(None, description="Average reach")
    smartFollowerCount: int | None = Field(None, description="Smart follower count")
    followerCount: int | None = Field(None, description="Total follower count")


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Remove None values from parameters dict."""
    return {k: v for k, v in params.items() if v is not None}
