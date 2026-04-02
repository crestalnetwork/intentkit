"""Tests for Moralis API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture
def mock_config():
    with patch("intentkit.clients.moralis.config") as mock:
        mock.moralis_api_key = "test-api-key"
        yield mock


@pytest.mark.asyncio
async def test_get_wallet_net_worth_success(mock_config):
    """Should return the net worth from Moralis API."""
    from intentkit.clients.moralis import get_wallet_net_worth

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"total_networth_usd": "1234.56"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("intentkit.clients.moralis._get_http_client", return_value=mock_client):
        result = await get_wallet_net_worth("0xabc123")

    assert result == 1234.56
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args
    assert "0xabc123" in call_kwargs.args[0]
    assert call_kwargs.kwargs["params"]["chains"] == ["eth", "base", "arbitrum", "bsc"]


@pytest.mark.asyncio
async def test_get_wallet_net_worth_no_api_key():
    """Should return 0.0 when no API key is configured."""
    from intentkit.clients.moralis import get_wallet_net_worth

    with patch("intentkit.clients.moralis.config") as mock_config:
        mock_config.moralis_api_key = None
        result = await get_wallet_net_worth("0xabc123")

    assert result == 0.0


@pytest.mark.asyncio
async def test_get_wallet_net_worth_api_error(mock_config):
    """Should return 0.0 on API error."""
    from intentkit.clients.moralis import get_wallet_net_worth

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
    )

    with patch("intentkit.clients.moralis._get_http_client", return_value=mock_client):
        result = await get_wallet_net_worth("0xabc123")

    assert result == 0.0


@pytest.mark.asyncio
async def test_get_wallet_net_worth_network_error(mock_config):
    """Should return 0.0 on network error."""
    from intentkit.clients.moralis import get_wallet_net_worth

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("intentkit.clients.moralis._get_http_client", return_value=mock_client):
        result = await get_wallet_net_worth("0xabc123")

    assert result == 0.0
