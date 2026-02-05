import logging
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from intentkit.utils.chain import InfuraChainProvider, SupportedNetwork

# Limit logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_infura_provider():
    api_key = "test_infura_key"
    provider = InfuraChainProvider(api_key)
    provider.init_chain_configs()

    expected_networks = [
        (SupportedNetwork.EthereumMainnet, "mainnet"),
        (SupportedNetwork.OptimismMainnet, "optimism-mainnet"),
        (SupportedNetwork.ArbitrumMainnet, "arbitrum-mainnet"),
        (SupportedNetwork.BnbMainnet, "bsc-mainnet"),
        (SupportedNetwork.BaseMainnet, "base-mainnet"),
        (SupportedNetwork.PolygonMainnet, "polygon-mainnet"),
    ]

    for net, subdomain in expected_networks:
        config = provider.chain_configs.get(net)
        if not config:
            logger.error(f"Missing config for {net}")
            continue

        expected_url = f"https://{subdomain}.infura.io/v3/{api_key}"
        if config.rpc_url != expected_url:
            logger.error(
                f"Incorrect RPC URL for {net}: {config.rpc_url} != {expected_url}"
            )
        else:
            logger.info(f"Verified {net}: {config.rpc_url}")


if __name__ == "__main__":
    test_infura_provider()
