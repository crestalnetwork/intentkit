"""BDD tests for on-chain ERC721 read-only skills using real RPC."""

import os

import pytest
import pytest_asyncio
from web3 import AsyncWeb3

from intentkit.skills.erc721.constants import ERC721_ABI

# Base mainnet network
NETWORK = "base-mainnet"
# Uniswap V3 Position Manager on Base - a well-known ERC721 contract
NFT_CONTRACT = "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1"
# An address unlikely to hold any Uniswap V3 positions
EMPTY_ADDRESS = "0x000000000000000000000000000000000000dEaD"


@pytest_asyncio.fixture(scope="module")
async def w3():
    """Create a real AsyncWeb3 client from env config."""
    infura_key = os.getenv("INFURA_API_KEY")
    if not infura_key:
        pytest.skip("No INFURA_API_KEY configured")

    rpc_url = f"https://base-mainnet.infura.io/v3/{infura_key}"
    provider = AsyncWeb3.AsyncHTTPProvider(rpc_url)
    client = AsyncWeb3(provider)

    connected = await client.is_connected()
    if not connected:
        pytest.skip("Cannot connect to RPC provider")

    return client


@pytest.mark.asyncio
async def test_erc721_balance_of(w3: AsyncWeb3):
    """balanceOf should return a non-negative integer for any address."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(NFT_CONTRACT),
        abi=ERC721_ABI,
    )
    balance = await contract.functions.balanceOf(
        w3.to_checksum_address(EMPTY_ADDRESS)
    ).call()
    assert isinstance(balance, int)
    assert balance >= 0


@pytest.mark.asyncio
async def test_erc721_supports_interface(w3: AsyncWeb3):
    """ERC721 contract should support the ERC721 interface (0x80ac58cd)."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(NFT_CONTRACT),
        abi=ERC721_ABI,
    )
    # ERC721 interface ID = 0x80ac58cd
    supports = await contract.functions.supportsInterface(
        bytes.fromhex("80ac58cd")
    ).call()
    assert supports is True


@pytest.mark.asyncio
async def test_erc721_supports_interface_erc165(w3: AsyncWeb3):
    """ERC721 contract should also support ERC165 (0x01ffc9a7)."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(NFT_CONTRACT),
        abi=ERC721_ABI,
    )
    supports = await contract.functions.supportsInterface(
        bytes.fromhex("01ffc9a7")
    ).call()
    assert supports is True
