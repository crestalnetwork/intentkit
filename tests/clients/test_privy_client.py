from typing import get_overloads, get_type_hints
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from web3.types import TxReceipt

from intentkit.clients import privy
from intentkit.clients.privy import PrivyClient


def _mock_async_client(
    mock_async_client_cls: MagicMock, response_json: dict[str, object]
) -> MagicMock:
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = response_json

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_async_client_cls.return_value = mock_cm
    return mock_client


class TestPrivyClient:
    @pytest.mark.asyncio
    async def test_create_key_quorum(self) -> None:
        with patch(
            "intentkit.clients.privy.httpx.AsyncClient"
        ) as mock_async_client_cls:
            mock_client = _mock_async_client(
                mock_async_client_cls,
                response_json={"id": "kq_test"},
            )

            privy = PrivyClient()
            privy.app_id = "app"
            privy.app_secret = "secret"
            privy.base_url = "https://api.privy.io/v1"

            key_quorum_id = await privy.create_key_quorum(
                user_ids=["did:privy:user"],
                authorization_threshold=1,
                display_name="intentkit:test",
            )

            assert key_quorum_id == "kq_test"
            args, kwargs = mock_client.post.call_args
            assert args[0] == "https://api.privy.io/v1/key_quorums"
            assert kwargs["json"] == {
                "user_ids": ["did:privy:user"],
                "authorization_threshold": 1,
                "display_name": "intentkit:test",
            }

    @pytest.mark.asyncio
    async def test_create_wallet_with_additional_signers(self) -> None:
        with patch(
            "intentkit.clients.privy.httpx.AsyncClient"
        ) as mock_async_client_cls:
            mock_client = _mock_async_client(
                mock_async_client_cls,
                response_json={
                    "id": "wallet_1",
                    "address": "0x0000000000000000000000000000000000000001",
                    "chain_type": "ethereum",
                },
            )

            privy = PrivyClient()
            privy.app_id = "app"
            privy.app_secret = "secret"
            privy.base_url = "https://api.privy.io/v1"

            wallet = await privy.create_wallet(additional_signer_ids=["kq_user"])

            assert wallet.id == "wallet_1"
            args, kwargs = mock_client.post.call_args
            assert args[0] == "https://api.privy.io/v1/wallets"
            assert kwargs["json"] == {
                "chain_type": "ethereum",
                "additional_signers": [{"signer_id": "kq_user"}],
            }

    @pytest.mark.asyncio
    async def test_create_wallet_with_owner_key_quorum(self) -> None:
        with patch(
            "intentkit.clients.privy.httpx.AsyncClient"
        ) as mock_async_client_cls:
            mock_client = _mock_async_client(
                mock_async_client_cls,
                response_json={
                    "id": "wallet_2",
                    "address": "0x0000000000000000000000000000000000000002",
                    "chain_type": "ethereum",
                },
            )

            privy = PrivyClient()
            privy.app_id = "app"
            privy.app_secret = "secret"
            privy.base_url = "https://api.privy.io/v1"

            wallet = await privy.create_wallet(owner_key_quorum_id="kq_owner")

            assert wallet.id == "wallet_2"
            args, kwargs = mock_client.post.call_args
            assert args[0] == "https://api.privy.io/v1/wallets"
            assert kwargs["json"] == {
                "chain_type": "ethereum",
                "owner_id": "kq_owner",
            }

    def test_get_authorization_public_keys_empty(self) -> None:
        privy = PrivyClient()
        privy._authorization_key_objects = []

        public_keys = privy.get_authorization_public_keys()

        assert public_keys == []

    def test_get_authorization_public_keys_with_key(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import ec

        privy = PrivyClient()
        # Generate a test P-256 key
        private_key = ec.generate_private_key(ec.SECP256R1())
        privy._authorization_key_objects = [private_key]

        public_keys = privy.get_authorization_public_keys()

        assert len(public_keys) == 1
        # Should be base64-encoded
        import base64

        decoded = base64.b64decode(public_keys[0])
        # SPKI DER format starts with specific bytes for P-256
        assert len(decoded) == 91  # Standard SPKI P-256 public key size


def test_send_transaction_with_master_wallet_overloads() -> None:
    overloads = get_overloads(privy._send_transaction_with_master_wallet)
    assert overloads
    returns = {get_type_hints(overload)["return"] for overload in overloads}
    assert str in returns
    assert tuple[str, TxReceipt] in returns
