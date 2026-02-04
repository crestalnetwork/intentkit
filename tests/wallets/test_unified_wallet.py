"""
Tests for unified wallet provider functionality.

These tests verify that the unified wallet provider and signer
interfaces work correctly for both CDP and Privy providers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets import get_wallet_provider, get_wallet_signer
from intentkit.wallets.signer import ThreadSafeEvmWalletSigner


class TestGetWalletProvider:
    """Tests for get_wallet_provider function."""

    @pytest.mark.asyncio
    async def test_cdp_provider(self):
        """Test getting wallet provider for CDP agent."""
        mock_agent = MagicMock()
        mock_agent.wallet_provider = "cdp"
        mock_agent.id = "test-agent"
        mock_agent.network_id = "base-mainnet"

        mock_cdp_provider = MagicMock()

        with patch(
            "intentkit.wallets.get_cdp_wallet_provider",
            new_callable=AsyncMock,
            return_value=mock_cdp_provider,
        ) as mock_get_cdp:
            provider = await get_wallet_provider(mock_agent)

            mock_get_cdp.assert_called_once_with(mock_agent)
            assert provider == mock_cdp_provider

    @pytest.mark.asyncio
    async def test_safe_provider(self):
        """Test getting wallet provider for Safe agent."""
        mock_agent = MagicMock()
        mock_agent.wallet_provider = "safe"
        mock_agent.id = "test-agent"
        mock_agent.network_id = "base-mainnet"

        mock_agent_data = MagicMock()
        mock_agent_data.privy_wallet_data = (
            '{"privy_wallet_id": "test-id", '
            '"privy_wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21", '
            '"smart_wallet_address": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", '
            '"network_id": "base-mainnet"}'
        )

        mock_privy_provider = MagicMock()

        with patch(
            "intentkit.models.agent_data.AgentData.get",
            new_callable=AsyncMock,
            return_value=mock_agent_data,
        ):
            with patch(
                "intentkit.wallets.privy.get_wallet_provider",
                return_value=mock_privy_provider,
            ):
                provider = await get_wallet_provider(mock_agent)
                assert provider is not None

    @pytest.mark.asyncio
    async def test_readonly_provider_raises(self):
        """Test that readonly wallet provider raises error."""
        mock_agent = MagicMock()
        mock_agent.wallet_provider = "readonly"
        mock_agent.id = "test-agent"

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_wallet_provider(mock_agent)

        assert exc_info.value.key == "ReadonlyWalletNotSupported"

    @pytest.mark.asyncio
    async def test_none_provider_raises(self):
        """Test that no wallet provider raises error."""
        mock_agent = MagicMock()
        mock_agent.wallet_provider = None
        mock_agent.id = "test-agent"

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_wallet_provider(mock_agent)

        assert exc_info.value.key == "NoWalletConfigured"

    @pytest.mark.asyncio
    async def test_unsupported_provider_raises(self):
        """Test that unsupported wallet provider raises error."""
        mock_agent = MagicMock()
        mock_agent.wallet_provider = "unknown"
        mock_agent.id = "test-agent"

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_wallet_provider(mock_agent)

        assert exc_info.value.key == "UnsupportedWalletProvider"


class TestEvmWallet:
    """Tests for EvmWallet class."""

    @pytest.mark.asyncio
    async def test_create_prefetches_address(self):
        """Test that create prefetches address and chain ID."""
        from intentkit.wallets.evm_wallet import EvmWallet

        mock_agent = MagicMock()
        mock_agent.wallet_provider = "cdp"
        mock_agent.network_id = "base-mainnet"

        mock_provider = MagicMock()
        mock_provider.get_address.return_value = "0x123"

        mock_w3 = MagicMock()
        mock_w3.eth.chain_id = 8453

        with (
            patch(
                "intentkit.wallets.evm_wallet.get_wallet_provider",
                new_callable=AsyncMock,
                return_value=mock_provider,
            ),
            patch(
                "intentkit.wallets.evm_wallet.get_web3_client",
                return_value=mock_w3,
            ),
        ):
            wallet = await EvmWallet.create(mock_agent)

        assert wallet.address == "0x123"
        assert wallet.chain_id == 8453


class TestGetWalletSigner:
    """Tests for get_wallet_signer function."""

    @pytest.mark.asyncio
    async def test_cdp_signer(self):
        """Test getting wallet signer for CDP agent."""
        mock_agent = MagicMock()
        mock_agent.wallet_provider = "cdp"
        mock_agent.id = "test-agent"
        mock_agent.network_id = "base-mainnet"

        mock_account = MagicMock()
        mock_account.address = "0x1234567890abcdef1234567890abcdef12345678"

        with patch(
            "intentkit.wallets.get_evm_account",
            new_callable=AsyncMock,
            return_value=mock_account,
        ):
            signer = await get_wallet_signer(mock_agent)

            assert signer is not None
            assert signer.address == mock_account.address

    @pytest.mark.asyncio
    async def test_readonly_signer_raises(self):
        """Test that readonly wallet signer raises error."""
        mock_agent = MagicMock()
        mock_agent.wallet_provider = "readonly"
        mock_agent.id = "test-agent"

        with pytest.raises(IntentKitAPIError) as exc_info:
            await get_wallet_signer(mock_agent)

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

        from eth_utils import to_checksum_address

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
