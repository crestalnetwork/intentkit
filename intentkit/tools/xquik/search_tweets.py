"""Search public X posts through Xquik."""

from decimal import Decimal
from typing import Any, Literal

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from intentkit.tools.xquik.base import XquikBaseTool


class XquikSearchTweetsInput(BaseModel):
    """Input parameters for searching public X posts."""

    q: str = Field(description="Search query, X status URL, or post ID")
    query_type: Literal["Latest", "Top"] = Field(
        default="Latest",
        description="Sort order for results",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Maximum posts to return (1-200)",
    )
    cursor: str | None = Field(
        default=None,
        description="Pagination cursor returned by a previous search",
    )

    @field_validator("q")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Reject empty and whitespace-only searches."""
        value = value.strip()
        if not value:
            raise ValueError("Search query must not be empty")
        return value


class XquikTweetAuthor(BaseModel):
    """Author fields returned by Xquik."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    username: str | None = None
    name: str | None = None
    verified: bool | None = None


class XquikTweet(BaseModel):
    """Public post fields returned by Xquik."""

    model_config = ConfigDict(extra="allow")

    id: str
    text: str | None = None
    createdAt: str | None = None
    likeCount: int | None = None
    retweetCount: int | None = None
    replyCount: int | None = None
    quoteCount: int | None = None
    viewCount: int | None = None
    bookmarkCount: int | None = None
    author: XquikTweetAuthor | None = None


class XquikSearchTweetsOutput(BaseModel):
    """Validated Xquik search response."""

    model_config = ConfigDict(extra="allow")

    tweets: list[XquikTweet] = Field(default_factory=list)
    has_next_page: bool
    next_cursor: str


def parse_search_response(payload: dict[str, Any]) -> XquikSearchTweetsOutput:
    """Validate required pagination and post fields."""
    try:
        return XquikSearchTweetsOutput.model_validate(payload)
    except ValidationError as exc:
        raise ToolException("Xquik API returned an unexpected response") from exc


class XquikSearchTweets(XquikBaseTool):
    """Search public X posts by query, post ID, or status URL."""

    name: str = "xquik_search_tweets"
    title: str = "Search X Posts"
    description: str = (
        "Search public X posts by query, post ID, or status URL through Xquik."
    )
    price: Decimal = Decimal("15")
    args_schema: ArgsSchema | None = XquikSearchTweetsInput

    async def _arun(
        self,
        q: str,
        query_type: Literal["Latest", "Top"] = "Latest",
        limit: int = 20,
        cursor: str | None = None,
        **_,
    ) -> XquikSearchTweetsOutput:
        """Run the Xquik search request."""
        payload = await self.get(
            "/x/tweets/search",
            params={
                "q": q,
                "queryType": query_type,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return parse_search_response(payload)
