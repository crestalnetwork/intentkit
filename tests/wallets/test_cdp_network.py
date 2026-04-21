"""Tests for get_cdp_network() in intentkit/wallets/cdp.py."""

from types import SimpleNamespace

import pytest

from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets.cdp import get_cdp_network


def _agent(network_id):
    """Return a minimal agent-like object with the given network_id."""
    return SimpleNamespace(network_id=network_id)


class TestGetCdpNetworkCanonicalNames:
    """Canonical network IDs that were already supported."""

    def test_base_mainnet(self):
        assert get_cdp_network(_agent("base-mainnet")) == "base"

    def test_ethereum_mainnet(self):
        assert get_cdp_network(_agent("ethereum-mainnet")) == "ethereum"

    def test_arbitrum_mainnet(self):
        assert get_cdp_network(_agent("arbitrum-mainnet")) == "arbitrum"

    def test_optimism_mainnet(self):
        assert get_cdp_network(_agent("optimism-mainnet")) == "optimism"

    def test_polygon_mainnet(self):
        assert get_cdp_network(_agent("polygon-mainnet")) == "polygon"

    def test_base_sepolia(self):
        assert get_cdp_network(_agent("base-sepolia")) == "base-sepolia"

    def test_bnb_mainnet(self):
        assert get_cdp_network(_agent("bnb-mainnet")) == "bsc"


class TestGetCdpNetworkAliases:
    """Network aliases that resolve via AGENT_NETWORK_TO_SUPPORTED_NETWORK."""

    def test_ethereum_alias(self):
        # "ethereum" is an alias for "ethereum-mainnet"
        assert get_cdp_network(_agent("ethereum")) == "ethereum"

    def test_polygon_alias(self):
        # "polygon" is an alias for "polygon-mainnet"
        assert get_cdp_network(_agent("polygon")) == "polygon"

    def test_matic_alias(self):
        # "matic" is an alias for "polygon-mainnet"
        assert get_cdp_network(_agent("matic")) == "polygon"

    def test_matic_mainnet_alias(self):
        assert get_cdp_network(_agent("matic-mainnet")) == "polygon"

    def test_bsc_mainnet_alias(self):
        # "bsc-mainnet" is an alias for "bnb-mainnet"
        assert get_cdp_network(_agent("bsc-mainnet")) == "bsc"

    def test_binance_mainnet_alias(self):
        # "binance-mainnet" is an alias for "bnb-mainnet"
        assert get_cdp_network(_agent("binance-mainnet")) == "bsc"


class TestGetCdpNetworkErrors:
    def test_missing_network_id_raises(self):
        with pytest.raises(IntentKitAPIError) as exc_info:
            get_cdp_network(_agent(None))
        assert exc_info.value.status_code == 400

    def test_empty_network_id_raises(self):
        with pytest.raises(IntentKitAPIError) as exc_info:
            get_cdp_network(_agent(""))
        assert exc_info.value.status_code == 400

    def test_solana_raises(self):
        with pytest.raises(IntentKitAPIError) as exc_info:
            get_cdp_network(_agent("solana"))
        assert exc_info.value.status_code == 400
        assert "Solana" in str(exc_info.value)

    def test_unknown_network_raises(self):
        with pytest.raises(IntentKitAPIError) as exc_info:
            get_cdp_network(_agent("not-a-real-network"))
        assert exc_info.value.status_code == 400
