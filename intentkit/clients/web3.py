from typing import Dict

from web3 import Web3

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.utils.chain import ChainProvider

# Global cache for Web3 clients by network_id
_web3_client_cache: Dict[str, Web3] = {}


def get_web3_client(network_id: str, skill_store: SkillStoreABC) -> Web3:
    """Get a Web3 client for the specified network.

    Args:
        network_id: The network ID to get the Web3 client for
        skill_store: The skill store to get system configuration from

    Returns:
        Web3: A Web3 client instance for the specified network
    """
    # Check global cache first
    if network_id in _web3_client_cache:
        return _web3_client_cache[network_id]

    # Create new Web3 client and cache it
    chain_provider: ChainProvider = skill_store.get_system_config("chain_provider")
    chain = chain_provider.get_chain_config(network_id)
    web3_client = Web3(Web3.HTTPProvider(chain.rpc_url))
    _web3_client_cache[network_id] = web3_client

    return web3_client
