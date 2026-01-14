from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from intentkit.clients.privy import PrivyClient
from intentkit.config.config import config


def _make_wallet_auth_key() -> str:
    private_key = ec.generate_private_key(ec.SECP256R1())
    der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return "wallet-auth:" + base64.b64encode(der).decode("utf-8")


@pytest.mark.asyncio
async def test_rpc_includes_privy_authorization_signature_header() -> None:
    wallet_auth_key = _make_wallet_auth_key()
    original_keys = getattr(config, "privy_authorization_private_keys", [])
    config.privy_authorization_private_keys = [wallet_auth_key]

    try:
        privy = PrivyClient()
        privy.app_id = "app"
        privy.app_secret = "secret"
        privy.base_url = "https://api.privy.io/v1"
        privy.authorization_private_keys = [wallet_auth_key]

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"data": {"signature": "0xsig"}}

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("intentkit.clients.privy.httpx.AsyncClient", return_value=mock_cm):
            await privy.sign_hash("wallet_1", b"\x11" * 32)

        _, kwargs = mock_client.post.call_args
        headers = kwargs["headers"]
        assert headers["privy-app-id"] == "app"
        assert "privy-authorization-signature" in headers
        assert isinstance(headers["privy-authorization-signature"], str)
        assert len(headers["privy-authorization-signature"]) > 0
    finally:
        config.privy_authorization_private_keys = original_keys
