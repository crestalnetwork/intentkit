"""
Tests for unified wallet provider functionality.

These tests verify that the unified wallet provider and signer
interfaces resolve a team wallet by address within the agent's team and
dispatch to the correct provider implementation (CDP, native,
Safe/Privy, readonly).
"""

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.wallet import TeamWallet
from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets import get_wallet_provider, get_wallet_signer
from intentkit.wallets.signer import ThreadSafeEvmWalletSigner

TEAM_ID = "team-1"
WALLET_ID = "wallet-1"
WALLET_ADDRESS = "0x1234567890abcdef1234567890abcdef12345678"


def _team_wallet(
    wallet_provider: str, wallet_data: dict[str, Any] | None = None
) -> TeamWallet:
    """Build a TeamWallet directly, bypassing the database."""
    now = datetime.now()
    return TeamWallet(
        id=WALLET_ID,
        team_id=TEAM_ID,
        name="main",
        wallet_provider=wallet_provider,
        network_id="base-mainnet",
        evm_wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        wallet_data=json.dumps(wallet_data) if wallet_data is not None else None,
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )


def _agent() -> MagicMock:
    """Build a fake agent belonging to the wallet's team."""
    agent = MagicMock()
    agent.id = "test-agent"
    agent.team_id = TEAM_ID
    agent.network_id = "base-mainnet"
    return agent


def _patch_wallet_get(wallet: TeamWallet | None):
    """Patch the by-address lookup so it resolves to the given wallet."""
    return patch(
        "intentkit.models.wallet.TeamWallet.get_by_address",
        new=AsyncMock(return_value=wallet),
    )


class TestGetWalletProvider:
    """Tests for get_wallet_provider function."""

    @pytest.mark.asyncio
    async def test_cdp_provider(self):
        """Test getting wallet provider for an agent bound to a CDP wallet."""
        mock_agent = _agent()
        wallet = _team_wallet("cdp")

        mock_cdp_provider = MagicMock()

        with (
            _patch_wallet_get(wallet),
            patch(
                "intentkit.wallets.get_cdp_wallet_provider",
                new_callable=AsyncMock,
                return_value=mock_cdp_provider,
            ) as mock_get_cdp,
        ):
            provider = await get_wallet_provider(mock_agent, WALLET_ADDRESS)

            mock_get_cdp.assert_called_once_with(wallet, mock_agent.network_id)
            assert provider == mock_cdp_provider

    @pytest.mark.asyncio
    async def test_safe_provider(self):
        """Test getting wallet provider for an agent bound to a Safe wallet."""
        mock_agent = _agent()
        wallet = _team_wallet(
            "safe",
            wallet_data={
                "privy_wallet_id": "test-id",
                "privy_wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
                "smart_wallet_address": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "network_id": "base-mainnet",
            },
        )

        mock_privy_provider = MagicMock()

        with (
            _patch_wallet_get(wallet),
            patch(
                "intentkit.wallets.get_privy_provider",
                return_value=mock_privy_provider,
            ) as mock_get_privy,
        ):
            provider = await get_wallet_provider(mock_agent, WALLET_ADDRESS)

            mock_get_privy.assert_called_once_with(wallet.wallet_data_json())
            assert provider == mock_privy_provider

    @pytest.mark.asyncio
    async def test_readonly_provider_raises(self):
        """Test that readonly wallet provider raises error."""
        mock_agent = _agent()
        wallet = _team_wallet("readonly")

        with _patch_wallet_get(wallet):
            with pytest.raises(IntentKitAPIError) as exc_info:
                await get_wallet_provider(mock_agent, WALLET_ADDRESS)

        assert exc_info.value.key == "ReadonlyWalletNotSupported"

    @pytest.mark.asyncio
    async def test_unknown_address_raises(self):
        """An address outside the team's wallet pool is rejected."""
        mock_agent = _agent()

        with _patch_wallet_get(None):
            with pytest.raises(IntentKitAPIError) as exc_info:
                await get_wallet_provider(mock_agent, WALLET_ADDRESS)

        assert exc_info.value.key == "WalletNotFound"

    @pytest.mark.asyncio
    async def test_unsupported_provider_raises(self):
        """Test that unsupported wallet provider raises error."""
        mock_agent = _agent()
        wallet = _team_wallet("unknown")

        with _patch_wallet_get(wallet):
            with pytest.raises(IntentKitAPIError) as exc_info:
                await get_wallet_provider(mock_agent, WALLET_ADDRESS)

        assert exc_info.value.key == "UnsupportedWalletProvider"


class TestEvmWallet:
    """Tests for EvmWallet class."""

    @pytest.mark.asyncio
    async def test_create_prefetches_address(self):
        """Test that create prefetches address and chain ID."""
        from intentkit.wallets.evm_wallet import EvmWallet

        mock_agent = _agent()

        mock_provider = MagicMock()
        mock_provider.get_address.return_value = "0x123"

        mock_w3 = MagicMock()
        import asyncio

        chain_id_mock = asyncio.Future()
        chain_id_mock.set_result(8453)
        mock_w3.eth.chain_id = chain_id_mock

        with (
            patch(
                "intentkit.wallets.evm_wallet.get_wallet_provider",
                new_callable=AsyncMock,
                return_value=mock_provider,
            ),
            patch(
                "intentkit.wallets.evm_wallet.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            wallet = await EvmWallet.create(mock_agent, WALLET_ADDRESS)

        assert wallet.address == "0x123"
        assert wallet.chain_id == 8453


class TestGetWalletSigner:
    """Tests for get_wallet_signer function."""

    @pytest.mark.asyncio
    async def test_cdp_signer(self):
        """Test getting wallet signer for an agent bound to a CDP wallet."""
        mock_agent = _agent()
        wallet = _team_wallet("cdp")

        mock_account = MagicMock()
        mock_account.address = "0x1234567890abcdef1234567890abcdef12345678"

        # Patch the CDP SDK's EvmLocalAccount: its real __init__ eagerly builds
        # an auth client from server_account.api_clients._cdp_client and validates
        # the credentials as strings, which a bare MagicMock cannot satisfy. We
        # only want to verify get_wallet_signer's cdp routing, not the SDK.
        with (
            _patch_wallet_get(wallet),
            patch(
                "intentkit.wallets.get_evm_account",
                new_callable=AsyncMock,
                return_value=mock_account,
            ) as mock_get_account,
            patch("cdp.EvmLocalAccount") as mock_local_account_class,
        ):
            mock_signer = MagicMock()
            mock_signer.address = mock_account.address
            mock_local_account_class.return_value = mock_signer

            signer = await get_wallet_signer(mock_agent, WALLET_ADDRESS)

            mock_get_account.assert_called_once_with(wallet)
            mock_local_account_class.assert_called_once_with(mock_account)
            assert signer is not None
            assert signer.address == mock_account.address

    @pytest.mark.asyncio
    async def test_readonly_signer_raises(self):
        """Test that readonly wallet signer raises error."""
        mock_agent = _agent()
        wallet = _team_wallet("readonly")

        with _patch_wallet_get(wallet):
            with pytest.raises(IntentKitAPIError) as exc_info:
                await get_wallet_signer(mock_agent, WALLET_ADDRESS)

        assert exc_info.value.key == "ReadonlyWalletNotSupported"


class TestThreadSafeEvmWalletSigner:
    """Tests for ThreadSafeEvmWalletSigner class."""

    def test_address_property(self):
        """Test that address property returns account address."""
        mock_account = MagicMock()
        mock_account.address = "0x1234567890abcdef"

        with patch(
            "intentkit.wallets.signer.EvmLocalAccount"
        ) as mock_local_account_class:
            mock_local_account = MagicMock()
            mock_local_account.address = mock_account.address
            mock_local_account_class.return_value = mock_local_account

            signer = ThreadSafeEvmWalletSigner(mock_account)
            address = signer.address

            mock_local_account_class.assert_called_once_with(mock_account)
            assert address == mock_account.address


class TestPrivyWalletSigner:
    """Tests for PrivyWalletSigner class."""

    def test_address_property(self):
        """Test that address property returns correct checksummed address."""
        from intentkit.wallets.privy import PrivyClient, PrivyWalletSigner

        mock_privy_client = MagicMock(spec=PrivyClient)
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21"

        signer = PrivyWalletSigner(
            privy_client=mock_privy_client,
            wallet_id="test-wallet-id",
            wallet_address=wallet_address,
        )

        from eth_utils.address import to_checksum_address

        expected_address = to_checksum_address(wallet_address)
        assert signer.address == expected_address

    def test_sign_transaction_not_implemented(self):
        """Test that sign_transaction raises NotImplementedError."""
        from intentkit.wallets.privy import PrivyClient, PrivyWalletSigner

        mock_privy_client = MagicMock(spec=PrivyClient)

        signer = PrivyWalletSigner(
            privy_client=mock_privy_client,
            wallet_id="test-wallet-id",
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
        )

        with pytest.raises(NotImplementedError):
            signer.sign_transaction({"to": "0x123", "value": 0})
