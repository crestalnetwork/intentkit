"""Tests for X402Order model."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

import intentkit.models.x402_order as x402_order_module
from intentkit.models.x402_order import (
    X402Order,
    X402OrderCreate,
    X402OrderTable,
)


@pytest.mark.asyncio
async def test_create_x402_order(monkeypatch):
    """Test creating an x402 order with all fields."""
    # Mock session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def mock_refresh(obj):
        obj.id = "order-123"
        obj.created_at = datetime.now()

    mock_session.refresh.side_effect = mock_refresh

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = mock_session
    mock_session_cls.__aexit__.return_value = None

    monkeypatch.setattr(x402_order_module, "get_session", lambda: mock_session_cls)

    order_create = X402OrderCreate(
        agent_id="agent-1",
        chat_id="chat-1",
        user_id="user-1",
        task_id="task-1",
        skill_name="x402_pay",
        method="POST",
        url="https://example.com/api",
        max_value=1000000,
        amount=500000,
        asset="USDC",
        network="base-mainnet",
        pay_to="0x1234567890abcdef",
        tx_hash="0xabcdef123456",
        status="success",
        error=None,
        http_status=200,
    )

    result = await X402Order.create(order_create)

    # Verify session usage
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called

    # Verify result
    assert isinstance(result, X402Order)
    assert result.agent_id == "agent-1"
    assert result.chat_id == "chat-1"
    assert result.user_id == "user-1"
    assert result.task_id == "task-1"
    assert result.skill_name == "x402_pay"
    assert result.method == "POST"
    assert result.url == "https://example.com/api"
    assert result.max_value == 1000000
    assert result.amount == 500000
    assert result.asset == "USDC"
    assert result.network == "base-mainnet"
    assert result.pay_to == "0x1234567890abcdef"
    assert result.tx_hash == "0xabcdef123456"
    assert result.status == "success"
    assert result.error is None
    assert result.http_status == 200
    assert result.id == "order-123"


@pytest.mark.asyncio
async def test_create_x402_order_minimal(monkeypatch):
    """Test creating an x402 order with only required fields."""
    # Mock session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def mock_refresh(obj):
        obj.id = "order-456"
        obj.created_at = datetime.now()

    mock_session.refresh.side_effect = mock_refresh

    mock_session_cls = MagicMock()
    mock_session_cls.__aenter__.return_value = mock_session
    mock_session_cls.__aexit__.return_value = None

    monkeypatch.setattr(x402_order_module, "get_session", lambda: mock_session_cls)

    order_create = X402OrderCreate(
        agent_id="agent-2",
        chat_id="chat-2",
        skill_name="x402_http_request",
        method="GET",
        url="https://example.com/resource",
        amount=100000,
        asset="USDC",
        network="base-sepolia",
        pay_to="0xabcdef1234567890",
        status="success",
    )

    result = await X402Order.create(order_create)

    # Verify result
    assert isinstance(result, X402Order)
    assert result.agent_id == "agent-2"
    assert result.user_id is None
    assert result.task_id is None
    assert result.max_value is None
    assert result.tx_hash is None
    assert result.error is None
    assert result.http_status is None
    assert result.id == "order-456"


def test_x402_order_table_model():
    """Test X402OrderTable model instantiation."""
    table = X402OrderTable(
        id="order-789",
        agent_id="agent-3",
        chat_id="chat-3",
        skill_name="x402_pay",
        method="POST",
        url="https://example.com",
        amount=200000,
        asset="USDC",
        network="base-mainnet",
        pay_to="0x9876543210",
        status="failed",
        error="Insufficient funds",
        created_at=datetime.now(),
    )

    assert table.id == "order-789"
    assert table.agent_id == "agent-3"
    assert table.status == "failed"
    assert table.error == "Insufficient funds"
