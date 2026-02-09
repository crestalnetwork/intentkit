from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets.native import (
    NativeWalletProvider,
    NativeWalletSigner,
    TransactionResult,
    create_native_wallet,
    get_wallet_provider,
    get_wallet_signer,
)


class TestNativeWalletProviderBasics:
    def test_get_wallet_provider_initialization(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=MagicMock()),
        ):
            provider = get_wallet_provider(native_data)

        assert isinstance(provider, NativeWalletProvider)
        from web3 import Web3

        assert provider.get_address() == Web3.to_checksum_address(
            native_data["address"]
        )

    @pytest.mark.asyncio
    async def test_get_address_async(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=MagicMock()),
        ):
            provider = get_wallet_provider(native_data)

        from web3 import Web3

        addr = await provider.get_address_async()
        assert addr == Web3.to_checksum_address(native_data["address"])

    @pytest.mark.asyncio
    async def test_get_balance(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()
        mock_w3.eth.get_balance.return_value = 12345

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=MagicMock()),
        ):
            provider = get_wallet_provider(native_data)

        bal = await provider.get_balance()
        assert bal == 12345


class TestNativeWalletProviderTransactions:
    @pytest.mark.asyncio
    async def test_execute_transaction_success_with_fee_history(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()
        mock_w3.eth.get_transaction_count.return_value = 1
        mock_w3.eth.chain_id = 8453
        mock_w3.eth.estimate_gas.return_value = 21000
        mock_w3.eth.fee_history.return_value = {"baseFeePerGas": [1000]}

        class _Signed:
            raw_transaction = b"raw"

        mock_account = MagicMock()
        mock_account.sign_transaction.return_value = _Signed()
        from hexbytes import HexBytes

        mock_w3.eth.send_raw_transaction.return_value = HexBytes("0xabc")

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=mock_account),
        ):
            provider = get_wallet_provider(native_data)
            res = await provider.execute_transaction(
                to="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", value=100
            )

        assert res.success is True
        assert str(res.tx_hash).lower().replace("0x", "") == "0abc"

    @pytest.mark.asyncio
    async def test_execute_transaction_legacy_gas_on_fee_history_error(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()
        mock_w3.eth.get_transaction_count.return_value = 2
        mock_w3.eth.chain_id = 8453
        mock_w3.eth.estimate_gas.return_value = 30000
        mock_w3.eth.fee_history.side_effect = Exception("no fee history")
        mock_w3.eth.gas_price = 99

        class _Signed:
            raw_transaction = b"raw"

        mock_account = MagicMock()

        def _sign_tx(params):
            return _Signed()

        mock_account.sign_transaction.side_effect = _sign_tx
        from hexbytes import HexBytes

        mock_w3.eth.send_raw_transaction.return_value = HexBytes("0xdef")

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=mock_account),
        ):
            provider = get_wallet_provider(native_data)
            res = await provider.execute_transaction(
                to="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", value=200
            )

        assert res.success is True
        assert str(res.tx_hash).lower().replace("0x", "") == "0def"

    @pytest.mark.asyncio
    async def test_transfer_erc20_delegates_to_execute_transaction(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()

        class _Func:
            def build_transaction(self, _):
                return {"data": "0xabcdef"}

        class _Functions:
            def transfer(self, to, amount):
                return _Func()

        class _Contract:
            functions = _Functions()

        mock_w3.eth.contract.return_value = _Contract()

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=MagicMock()),
        ):
            provider = get_wallet_provider(native_data)
            with patch.object(
                provider,
                "execute_transaction",
                new_callable=AsyncMock,
                return_value=TransactionResult(success=True, tx_hash="0xaaa"),
            ) as mock_exec:
                res = await provider.transfer_erc20(
                    token_address="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                    to="0x0000000000000000000000000000000000000001",
                    amount=5,
                )

        assert res.success is True
        args, kwargs = mock_exec.call_args
        assert kwargs["to"] == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        assert kwargs["value"] == 0
        assert isinstance(kwargs["data"], bytes)

    @pytest.mark.asyncio
    async def test_get_erc20_balance(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()

        class _BalanceOf:
            def call(self):
                return 777

        class _Functions:
            def balanceOf(self, _):
                return _BalanceOf()

        class _Contract:
            functions = _Functions()

        mock_w3.eth.contract.return_value = _Contract()

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=MagicMock()),
        ):
            provider = get_wallet_provider(native_data)
            bal = await provider.get_erc20_balance(
                token_address="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
            )

        assert bal == 777

    def test_native_transfer_success(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=MagicMock()),
        ):
            provider = get_wallet_provider(native_data)

        async def _ok(*args, **kwargs):
            return TransactionResult(success=True, tx_hash="0xbbb")

        with patch.object(
            provider, "execute_transaction", new=AsyncMock(side_effect=_ok)
        ) as mock_exec:
            txh = provider.native_transfer(
                to="0x0000000000000000000000000000000000000001",
                value=Decimal("1.5"),
            )

        assert txh == "0xbbb"
        args, kwargs = mock_exec.call_args
        assert kwargs["to"] == "0x0000000000000000000000000000000000000001"
        assert kwargs["value"] == int(Decimal("1.5") * Decimal(10**18))

    def test_native_transfer_failure_raises(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
            "network_id": "base-mainnet",
        }

        mock_w3 = MagicMock()

        with (
            patch("intentkit.wallets.native.get_web3_client", return_value=mock_w3),
            patch("eth_account.Account.from_key", return_value=MagicMock()),
        ):
            provider = get_wallet_provider(native_data)

        async def _fail(*args, **kwargs):
            return TransactionResult(success=False, error="x")

        with patch.object(
            provider, "execute_transaction", new=AsyncMock(side_effect=_fail)
        ):
            with pytest.raises(IntentKitAPIError):
                provider.native_transfer(
                    to="0x0000000000000000000000000000000000000001",
                    value=Decimal("0.1"),
                )


class TestNativeWalletSigner:
    def test_address_property(self):
        with patch("eth_account.Account.from_key", return_value=MagicMock()):
            signer = NativeWalletSigner(
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
                private_key="0x0123",
            )
        from web3 import Web3

        assert signer.address == Web3.to_checksum_address(
            "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21"
        )

    def test_sign_message(self):
        mock_account = MagicMock()
        mock_account.sign_message.return_value = "signed"
        with patch("eth_account.Account.from_key", return_value=mock_account):
            signer = NativeWalletSigner(
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
                private_key="0x0123",
            )
        msg = MagicMock()
        res = signer.sign_message(msg)
        assert res == "signed"
        mock_account.sign_message.assert_called_once_with(msg)

    def test_sign_transaction(self):
        mock_account = MagicMock()
        mock_account.sign_transaction.return_value = "signed_tx"
        with patch("eth_account.Account.from_key", return_value=mock_account):
            signer = NativeWalletSigner(
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
                private_key="0x0123",
            )
        tx = {"to": "0x1", "value": 0}
        res = signer.sign_transaction(tx)
        assert res == "signed_tx"
        mock_account.sign_transaction.assert_called_once_with(tx)

    def test_sign_typed_data_full_message(self):
        mock_account = MagicMock()
        with (
            patch("eth_account.Account.from_key", return_value=mock_account),
            patch("eth_account.messages.encode_typed_data", return_value=MagicMock()),
        ):
            signer = NativeWalletSigner(
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
                private_key="0x0123",
            )
            res = signer.sign_typed_data(
                full_message={"types": {}, "domain": {}, "message": {}}
            )
        assert res == mock_account.sign_message.return_value
        assert mock_account.sign_message.called

    def test_sign_typed_data_args(self):
        mock_account = MagicMock()
        with (
            patch("eth_account.Account.from_key", return_value=mock_account),
            patch("eth_account.messages.encode_typed_data", return_value=MagicMock()),
        ):
            signer = NativeWalletSigner(
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
                private_key="0x0123",
            )
            res = signer.sign_typed_data(
                domain_data={}, message_types={}, message_data={}
            )
        assert res == mock_account.sign_message.return_value
        assert mock_account.sign_message.called

    def test_unsafe_sign_hash(self):
        mock_account = MagicMock()
        mock_account.unsafe_sign_hash.return_value = "unsafe"
        with patch("eth_account.Account.from_key", return_value=mock_account):
            signer = NativeWalletSigner(
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
                private_key="0x0123",
            )
        from hexbytes import HexBytes

        res = signer.unsafe_sign_hash(HexBytes(b"\x00" * 32))
        assert res == "unsafe"
        mock_account.unsafe_sign_hash.assert_called_once()


class TestNativeWalletFactory:
    def test_create_native_wallet(self):
        mock_account = SimpleNamespace(
            address="0x0000000000000000000000000000000000000001",
            key=SimpleNamespace(hex=lambda: "0xabc"),
        )
        with patch("eth_account.Account.create", return_value=mock_account):
            result = create_native_wallet("base-mainnet")
        assert result["address"] == mock_account.address
        assert result["private_key"] == "0xabc"
        assert result["network_id"] == "base-mainnet"

    def test_get_wallet_signer(self):
        native_data = {
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
            "private_key": "0x0123",
        }
        with patch("eth_account.Account.from_key", return_value=MagicMock()):
            signer = get_wallet_signer(native_data)
        assert isinstance(signer, NativeWalletSigner)
