from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

from web3 import Web3


def load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "transfer_cdp_agent_wallets.py"
    )
    spec = spec_from_file_location("transfer_cdp_agent_wallets", script_path)
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load script module")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_owner_address_prefers_evm_wallet():
    module = load_script_module()
    user = SimpleNamespace(
        id="not-an-address",
        evm_wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
    )
    assert module.resolve_owner_address(user) == Web3.to_checksum_address(
        user.evm_wallet_address
    )


def test_resolve_owner_address_falls_back_to_id():
    module = load_script_module()
    user = SimpleNamespace(
        id="0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
        evm_wallet_address=None,
    )
    assert module.resolve_owner_address(user) == Web3.to_checksum_address(user.id)


def test_resolve_owner_address_returns_none_for_invalid():
    module = load_script_module()
    user = SimpleNamespace(id="not-address", evm_wallet_address=None)
    assert module.resolve_owner_address(user) is None


def test_compute_transferable_eth_wei():
    module = load_script_module()
    assert module.compute_transferable_eth_wei(1000, 2000) == 0
    assert module.compute_transferable_eth_wei(5000, 2000) == 3000


def test_format_token_amount():
    module = load_script_module()
    assert module.format_token_amount(Decimal("0"), 6) == "0"
    assert module.format_token_amount(Decimal("1.230000"), 6) == "1.23"
    assert module.format_token_amount(Decimal("1.234567"), 6) == "1.234567"
