"""Tests for the Xquik toolset."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from langchain_core.tools.base import ToolException
from pydantic import ValidationError

from intentkit.tools.xquik import available, get_tools, toolset
from intentkit.tools.xquik.search_tweets import (
    XquikSearchTweets,
    XquikSearchTweetsInput,
    parse_search_response,
)


def _response(payload: object, status_code: int = 200) -> httpx.Response:
    """Build an HTTP response with a request for raise_for_status()."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://xquik.com/api/v1/x/tweets/search"),
    )


def test_toolset_and_tool_metadata() -> None:
    """Expose repository-native catalog metadata and tool fields."""
    tool = XquikSearchTweets()

    assert toolset.title == "Xquik"
    assert toolset.tags == ["Search", "Social"]
    assert toolset.icon == "/tools/xquik/xquik.svg"
    assert "Not affiliated with X Corp." in toolset.description
    assert tool.name == "xquik_search_tweets"
    assert tool.title == "Search X Posts"
    assert tool.price == Decimal("15")
    assert tool.category == "xquik"


@pytest.mark.parametrize("q", ["", "   "])
def test_input_rejects_empty_queries(q: str) -> None:
    """Reject empty and whitespace-only searches before an API call."""
    with pytest.raises(ValidationError):
        XquikSearchTweetsInput(q=q)


def test_input_applies_defaults_and_bounds() -> None:
    """Keep request size bounded while preserving the API sort contract."""
    request = XquikSearchTweetsInput(q="  agent frameworks  ")

    assert request.q == "agent frameworks"
    assert request.query_type == "Latest"
    assert request.limit == 20

    with pytest.raises(ValidationError):
        XquikSearchTweetsInput(q="agents", limit=0)
    with pytest.raises(ValidationError):
        XquikSearchTweetsInput(q="agents", limit=201)


def test_available_reflects_api_key_configuration() -> None:
    """Hide the toolset unless its hosted credential is configured."""
    with patch("intentkit.tools.xquik.system_config") as system_config:
        system_config.xquik_api_key = "test-key"
        assert available() is True

        system_config.xquik_api_key = None
        assert available() is False


@pytest.mark.asyncio
async def test_get_tools_returns_known_names_only() -> None:
    """Resolve requested tools through the current toolset entrypoint."""
    tools = await get_tools(["unknown", "xquik_search_tweets"])

    assert [tool.name for tool in tools] == ["xquik_search_tweets"]


def test_search_response_requires_contract_fields() -> None:
    """Reject malformed payloads instead of returning partial results."""
    invalid_payloads = [
        {"tweets": "not-a-list", "has_next_page": False, "next_cursor": ""},
        {"tweets": [], "has_next_page": False},
        {"tweets": [{"text": "missing id"}], "has_next_page": False, "next_cursor": ""},
    ]

    for payload in invalid_payloads:
        with pytest.raises(ToolException, match="unexpected response"):
            parse_search_response(payload)


@pytest.mark.asyncio
async def test_search_calls_current_xquik_contract() -> None:
    """Send the documented route, authentication header, and query fields."""
    payload = {
        "tweets": [
            {
                "id": "123",
                "text": "IntentKit adds a new data source.",
                "author": {"username": "example"},
            }
        ],
        "has_next_page": True,
        "next_cursor": "cursor-1",
    }

    with patch("intentkit.tools.xquik.base.config") as config:
        config.xquik_api_key = "test-key"
        with patch("intentkit.tools.xquik.base.httpx.AsyncClient") as client_class:
            client = AsyncMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client.get = AsyncMock(return_value=_response(payload))
            client_class.return_value = client

            output = await XquikSearchTweets()._arun(
                q="intentkit",
                query_type="Top",
                limit=5,
                cursor="start",
            )

    assert output.tweets[0].id == "123"
    assert output.tweets[0].author is not None
    assert output.tweets[0].author.username == "example"
    assert output.next_cursor == "cursor-1"
    client_class.assert_called_once_with(timeout=30.0)
    client.get.assert_awaited_once()
    args, kwargs = client.get.await_args
    assert args == ("https://xquik.com/api/v1/x/tweets/search",)
    assert kwargs["headers"] == {
        "accept": "application/json",
        "x-api-key": "test-key",
    }
    assert kwargs["params"] == {
        "q": "intentkit",
        "queryType": "Top",
        "limit": 5,
        "cursor": "start",
    }


@pytest.mark.asyncio
async def test_search_requires_api_key() -> None:
    """Fail before networking when the hosted credential is absent."""
    with patch("intentkit.tools.xquik.base.config") as config:
        config.xquik_api_key = None
        with pytest.raises(ToolException, match="API key is not configured"):
            await XquikSearchTweets()._arun(q="intentkit")


@pytest.mark.asyncio
async def test_http_errors_are_sanitized() -> None:
    """Report status without returning an upstream response body."""
    with patch("intentkit.tools.xquik.base.config") as config:
        config.xquik_api_key = "test-key"
        with patch("intentkit.tools.xquik.base.httpx.AsyncClient") as client_class:
            client = AsyncMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client.get = AsyncMock(return_value=_response({"secret": "body"}, 402))
            client_class.return_value = client

            with pytest.raises(ToolException, match="returned HTTP 402") as error:
                await XquikSearchTweets()._arun(q="intentkit")

    assert "secret" not in str(error.value)


@pytest.mark.asyncio
async def test_request_and_json_errors_are_stable() -> None:
    """Convert transport and decoding failures into stable tool errors."""
    with patch("intentkit.tools.xquik.base.config") as config:
        config.xquik_api_key = "test-key"
        with patch("intentkit.tools.xquik.base.httpx.AsyncClient") as client_class:
            client = AsyncMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client_class.return_value = client

            client.get = AsyncMock(
                side_effect=httpx.ConnectError(
                    "connection details",
                    request=httpx.Request("GET", "https://xquik.com"),
                )
            )
            with pytest.raises(ToolException, match="request failed") as error:
                await XquikSearchTweets()._arun(q="intentkit")
            assert "connection details" not in str(error.value)

            invalid_json = httpx.Response(
                status_code=200,
                content=b"not-json",
                request=httpx.Request(
                    "GET", "https://xquik.com/api/v1/x/tweets/search"
                ),
            )
            client.get = AsyncMock(return_value=invalid_json)
            with pytest.raises(ToolException, match="invalid JSON"):
                await XquikSearchTweets()._arun(q="intentkit")
