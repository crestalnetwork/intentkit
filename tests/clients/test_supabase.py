"""Tests for Supabase identity client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_config():
    with patch("intentkit.clients.supabase.config") as mock:
        mock.supabase_url = "https://test.supabase.co"
        mock.supabase_service_role_key = "test-service-role-key"
        yield mock


@pytest.fixture
def sample_identities():
    return [
        {
            "id": "google-identity-id",
            "provider": "google",
            "identity_data": {
                "email": "user@gmail.com",
                "full_name": "Test User",
            },
        },
        {
            "id": "web3-identity-id",
            "provider": "web3",
            "identity_data": {
                "address": "0xabc123def456",
                "chain": "ethereum",
            },
        },
    ]


class TestParseLinkedProviders:
    def test_both_providers(self, sample_identities):
        from intentkit.clients.supabase import parse_linked_providers

        result = parse_linked_providers(sample_identities)

        assert "google" in result
        assert result["google"]["email"] == "user@gmail.com"
        assert result["google"]["identity_id"] == "google-identity-id"
        assert result["google"]["linked"] is True

        assert "evm" in result
        assert result["evm"]["address"] == "0xabc123def456"
        assert result["evm"]["identity_id"] == "web3-identity-id"
        assert result["evm"]["linked"] is True

    def test_google_only(self):
        from intentkit.clients.supabase import parse_linked_providers

        identities = [
            {
                "id": "google-id",
                "provider": "google",
                "identity_data": {"email": "a@b.com"},
            }
        ]
        result = parse_linked_providers(identities)
        assert "google" in result
        assert "evm" not in result

    def test_web3_solana_not_evm(self):
        from intentkit.clients.supabase import parse_linked_providers

        identities = [
            {
                "id": "sol-id",
                "provider": "web3",
                "identity_data": {"address": "SolAddr", "chain": "solana"},
            }
        ]
        result = parse_linked_providers(identities)
        assert "evm" not in result

    def test_empty_identities(self):
        from intentkit.clients.supabase import parse_linked_providers

        result = parse_linked_providers([])
        assert result == {}


@pytest.mark.asyncio
async def test_get_user_identities_success(mock_config, sample_identities):
    from intentkit.clients.supabase import get_user_identities

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"identities": sample_identities}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("intentkit.clients.supabase._get_http_client", return_value=mock_client):
        result = await get_user_identities("user-123")

    assert len(result) == 2
    assert result[0]["provider"] == "google"


@pytest.mark.asyncio
async def test_get_user_identities_not_configured():
    from intentkit.clients.supabase import get_user_identities

    with patch("intentkit.clients.supabase.config") as mock:
        mock.supabase_url = None
        mock.supabase_service_role_key = None
        result = await get_user_identities("user-123")

    assert result == []


@pytest.mark.asyncio
async def test_get_user_identities_api_error(mock_config):
    from intentkit.clients.supabase import get_user_identities

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Network error"))

    with patch("intentkit.clients.supabase._get_http_client", return_value=mock_client):
        result = await get_user_identities("user-123")

    assert result == []


@pytest.mark.asyncio
async def test_unlink_identity_success(mock_config):
    from intentkit.clients.supabase import unlink_identity

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.delete = AsyncMock(return_value=mock_resp)

    with patch("intentkit.clients.supabase._get_http_client", return_value=mock_client):
        result = await unlink_identity("user-123", "identity-456")

    assert result is True
    mock_client.delete.assert_called_once()
    call_url = mock_client.delete.call_args.args[0]
    assert "user-123" in call_url
    assert "identity-456" in call_url


@pytest.mark.asyncio
async def test_unlink_identity_failure(mock_config):
    from intentkit.clients.supabase import unlink_identity

    mock_client = AsyncMock()
    mock_client.delete = AsyncMock(side_effect=Exception("API error"))

    with patch("intentkit.clients.supabase._get_http_client", return_value=mock_client):
        result = await unlink_identity("user-123", "identity-456")

    assert result is False


@pytest.mark.asyncio
async def test_unlink_identity_not_configured():
    from intentkit.clients.supabase import unlink_identity

    with patch("intentkit.clients.supabase.config") as mock:
        mock.supabase_url = None
        mock.supabase_service_role_key = None
        result = await unlink_identity("user-123", "identity-456")

    assert result is False
