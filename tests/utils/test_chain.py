import pytest

from intentkit.utils.chain import (
    Chain,
    ChainConfig,
    ChainProvider,
    Network,
    NetworkId,
)


class DummyChainProvider(ChainProvider):
    def __init__(self):
        super().__init__()
        self.chain_configs = {
            Network.BaseMainnet: ChainConfig(
                chain=Chain.Base,
                network=Network.BaseMainnet,
                rpc_url="https://example-rpc",
                ens_url="https://example-ens",
                wss_url="wss://example",
            )
        }

    def init_chain_configs(self, api_key: str):
        return self.chain_configs


def test_chain_config_properties():
    config = ChainConfig(
        chain=Chain.Ethereum,
        network=Network.EthereumMainnet,
        rpc_url="https://eth",
        ens_url="https://ens",
        wss_url="wss://eth",
    )

    assert config.chain is Chain.Ethereum
    assert config.network is Network.EthereumMainnet
    assert config.network_id == NetworkId.EthereumMainnet
    assert config.rpc_url == "https://eth"
    assert config.ens_url == "https://ens"
    assert config.wss_url == "wss://eth"


def test_chain_provider_fetch_by_network_and_id():
    provider = DummyChainProvider()

    config = provider.get_chain_config(Network.BaseMainnet)
    assert config.rpc_url == "https://example-rpc"

    config_by_id = provider.get_chain_config_by_id(NetworkId.BaseMainnet)
    assert config_by_id is config


def test_chain_provider_missing_network():
    provider = DummyChainProvider()

    with pytest.raises(Exception) as exc:
        provider.get_chain_config(Network.EthereumSepolia)

    assert "chain config for network" in str(exc.value)


def test_chain_provider_missing_network_id():
    provider = DummyChainProvider()

    with pytest.raises(Exception) as exc:
        provider.get_chain_config_by_id(NetworkId.GnosisMainnet)

    assert "chain config for network" in str(exc.value)
