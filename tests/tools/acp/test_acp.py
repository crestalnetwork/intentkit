"""Tests for ACP tools."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from intentkit.tools.acp import available, get_tools
from intentkit.tools.acp.cancel_checkout import (
    AcpCancelCheckout,
    AcpCancelCheckoutInput,
)
from intentkit.tools.acp.complete_checkout import (
    AcpCompleteCheckout,
    AcpCompleteCheckoutInput,
)
from intentkit.tools.acp.create_checkout import (
    AcpCreateCheckout,
    AcpCreateCheckoutInput,
)
from intentkit.tools.acp.get_checkout import AcpGetCheckout
from intentkit.tools.acp.list_products import AcpListProducts, AcpListProductsInput

# --- Metadata tests ---


def test_tool_metadata():
    """Test tool names and categories."""
    cases = [
        (AcpListProducts, "acp_list_products"),
        (AcpCreateCheckout, "acp_create_checkout"),
        (AcpGetCheckout, "acp_get_checkout"),
        (AcpCompleteCheckout, "acp_complete_checkout"),
        (AcpCancelCheckout, "acp_cancel_checkout"),
    ]
    for cls, expected_name in cases:
        tool = cls()
        assert tool.name == expected_name
        assert tool.category == "acp"


def test_available():
    assert available() is True


@pytest.mark.asyncio
async def test_get_tools_all_names():
    names = [
        "acp_list_products",
        "acp_create_checkout",
        "acp_get_checkout",
        "acp_complete_checkout",
        "acp_cancel_checkout",
    ]
    tools = await get_tools(names)
    assert [t.name for t in tools] == names


@pytest.mark.asyncio
async def test_get_tools_empty_selection():
    assert await get_tools([]) == []


@pytest.mark.asyncio
async def test_get_tools_skips_unknown_names():
    tools = await get_tools(["acp_list_products", "acp_bogus"])
    assert [t.name for t in tools] == ["acp_list_products"]


# --- Input validation tests ---


def test_list_products_input():
    inp = AcpListProductsInput(merchant_url="https://example.com")
    assert inp.merchant_url == "https://example.com"
    assert inp.timeout == 30.0


def test_create_checkout_input():
    inp = AcpCreateCheckoutInput(
        merchant_url="https://example.com",
        items=[{"product_id": "prod_001", "quantity": 2}],
    )
    assert len(inp.items) == 1
    assert inp.items[0]["product_id"] == "prod_001"


def test_complete_checkout_input():
    inp = AcpCompleteCheckoutInput(
        merchant_url="https://example.com",
        session_id="session_123",
        tx_hash="0xabc",
    )
    assert inp.session_id == "session_123"
    assert inp.tx_hash == "0xabc"


def test_cancel_checkout_input():
    inp = AcpCancelCheckoutInput(
        merchant_url="https://example.com",
        session_id="session_123",
    )
    assert inp.session_id == "session_123"


# --- Tool execution tests (mocked HTTP) ---


def _make_mock_response(
    json_data: dict | list, status_code: int = 200
) -> httpx.Response:
    """Create a mock httpx.Response."""
    import json

    return httpx.Response(
        status_code=status_code,
        content=json.dumps(json_data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://example.com"),
    )


@pytest.mark.asyncio
async def test_list_products_execution():
    tool = AcpListProducts()

    mock_products = [
        {
            "id": "prod_001",
            "name": "Test Product",
            "description": "A test",
            "price": 10000,
        },
    ]

    with patch("intentkit.tools.acp.base.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request = AsyncMock(return_value=_make_mock_response(mock_products))
        mock_client_class.return_value = mock_client

        result = await tool._arun(merchant_url="https://example.com")
        assert "prod_001" in result
        assert "Test Product" in result
        assert "$0.01" in result


@pytest.mark.asyncio
async def test_create_checkout_execution():
    tool = AcpCreateCheckout()

    mock_session = {
        "id": "session_abc",
        "status": "created",
        "total_amount": 40000,
        "payment_url": "https://example.com/checkout_sessions/session_abc/x402_pay",
        "items": [{"product_id": "prod_001", "quantity": 1}],
    }

    with patch("intentkit.tools.acp.base.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request = AsyncMock(return_value=_make_mock_response(mock_session))
        mock_client_class.return_value = mock_client

        result = await tool._arun(
            merchant_url="https://example.com",
            items=[{"product_id": "prod_001", "quantity": 1}],
        )
        assert "session_abc" in result
        assert "x402_pay" in result
        assert "40000" in result
        assert "x402_pay" in result


@pytest.mark.asyncio
async def test_complete_checkout_execution():
    tool = AcpCompleteCheckout()

    mock_completed = {
        "id": "session_abc",
        "status": "completed",
        "total_amount": 40000,
        "tx_hash": "0xdef456",
    }

    with patch("intentkit.tools.acp.base.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request = AsyncMock(
            return_value=_make_mock_response(mock_completed)
        )
        mock_client_class.return_value = mock_client

        result = await tool._arun(
            merchant_url="https://example.com",
            session_id="session_abc",
            tx_hash="0xdef456",
        )
        assert "completed" in result.lower()
        assert "session_abc" in result
        assert "0xdef456" in result


@pytest.mark.asyncio
async def test_cancel_checkout_execution():
    tool = AcpCancelCheckout()

    mock_cancelled = {
        "id": "session_abc",
        "status": "cancelled",
    }

    with patch("intentkit.tools.acp.base.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request = AsyncMock(
            return_value=_make_mock_response(mock_cancelled)
        )
        mock_client_class.return_value = mock_client

        result = await tool._arun(
            merchant_url="https://example.com",
            session_id="session_abc",
        )
        assert "cancelled" in result
        assert "session_abc" in result
