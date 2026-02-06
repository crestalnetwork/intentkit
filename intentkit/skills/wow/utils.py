"""Utility functions for WOW skills."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from web3 import Web3

from intentkit.skills.wow.constants import (
    ADDRESSES,
    UNISWAP_QUOTER_ABI,
    UNISWAP_V3_ABI,
    WOW_ABI,
    WOW_FACTORY_CONTRACT_ADDRESSES,
)

if TYPE_CHECKING:
    from intentkit.wallets.evm_wallet import EvmWallet

logger = logging.getLogger(__name__)


@dataclass
class PoolInfo:
    """Pool info for a given Uniswap V3 pool."""

    token0: str
    balance0: int
    token1: str
    balance1: int
    fee: int
    liquidity: int
    sqrt_price_x96: int


@dataclass
class Quote:
    """Quote for a given Uniswap V3 swap."""

    amount_in: int
    amount_out: int
    fee: float | None
    error: str | None


def get_network_from_chain_id(chain_id: int | str | None) -> str:
    """Get network name from chain ID.

    Args:
        chain_id: The chain ID.

    Returns:
        The network name ('base-mainnet' or 'base-sepolia').
    """
    if chain_id is None:
        return "base-mainnet"
    chain_id_str = str(chain_id)
    return "base-mainnet" if chain_id_str == "8453" else "base-sepolia"


def get_factory_address(chain_id: int | str | None) -> str:
    """Get the Zora WOW ERC20 Factory contract address for the specified network.

    Args:
        chain_id: The chain ID.

    Returns:
        The contract address for the specified network.

    Raises:
        ValueError: If the specified network is not supported.
    """
    network = get_network_from_chain_id(chain_id)
    if network not in WOW_FACTORY_CONTRACT_ADDRESSES:
        raise ValueError(
            f"Invalid network: {network}. "
            f"Valid networks are: {', '.join(WOW_FACTORY_CONTRACT_ADDRESSES.keys())}"
        )
    return WOW_FACTORY_CONTRACT_ADDRESSES[network]


async def get_has_graduated(wallet: "EvmWallet", token_address: str) -> bool:
    """Check if a token has graduated from the Zora WOW protocol.

    Graduated tokens trade on Uniswap V3 instead of the bonding curve.

    Args:
        wallet: The unified wallet instance.
        token_address: Token contract address.

    Returns:
        True if the token has graduated, False otherwise.
    """
    try:
        market_type = await wallet.call_contract(
            contract_address=token_address,
            abi=WOW_ABI,
            function_name="marketType",
            args=[],
        )
        return market_type == 1
    except Exception as e:
        logger.warning(f"Error checking graduation status: {e}")
        return False


async def get_buy_quote(
    wallet: "EvmWallet",
    token_address: str,
    amount_eth_in_wei: str | int,
) -> int:
    """Get quote for buying tokens with ETH.

    Args:
        wallet: The unified wallet instance.
        token_address: Token contract address.
        amount_eth_in_wei: Amount of ETH to spend (in wei).

    Returns:
        The amount of tokens that would be received.
    """
    amount_eth_in_wei_int = int(amount_eth_in_wei)
    has_graduated = await get_has_graduated(wallet, token_address)

    if has_graduated:
        # Use Uniswap quote for graduated tokens
        quote = await get_uniswap_quote(
            wallet, token_address, amount_eth_in_wei_int, "buy"
        )
        if quote.amount_out > 0:
            return quote.amount_out

    # Use bonding curve quote
    try:
        token_quote = await wallet.call_contract(
            contract_address=token_address,
            abi=WOW_ABI,
            function_name="getEthBuyQuote",
            args=[amount_eth_in_wei_int],
        )

        # Handle tuple/list response
        if isinstance(token_quote, list | tuple):
            return int(token_quote[0]) if token_quote else 0
        return int(token_quote)
    except Exception as e:
        logger.warning(f"Error getting buy quote: {e}")
        return 0


async def get_sell_quote(
    wallet: "EvmWallet",
    token_address: str,
    amount_tokens_in_wei: str | int,
) -> int:
    """Get quote for selling tokens for ETH.

    Args:
        wallet: The unified wallet instance.
        token_address: Token contract address.
        amount_tokens_in_wei: Amount of tokens to sell (in wei).

    Returns:
        The amount of ETH that would be received.
    """
    amount_tokens_in_wei_int = int(amount_tokens_in_wei)
    has_graduated = await get_has_graduated(wallet, token_address)

    if has_graduated:
        # Use Uniswap quote for graduated tokens
        quote = await get_uniswap_quote(
            wallet, token_address, amount_tokens_in_wei_int, "sell"
        )
        if quote.amount_out > 0:
            return quote.amount_out

    # Use bonding curve quote
    try:
        eth_quote = await wallet.call_contract(
            contract_address=token_address,
            abi=WOW_ABI,
            function_name="getTokenSellQuote",
            args=[amount_tokens_in_wei_int],
        )

        # Handle tuple/list response
        if isinstance(eth_quote, list | tuple):
            return int(eth_quote[0]) if eth_quote else 0
        return int(eth_quote)
    except Exception as e:
        logger.warning(f"Error getting sell quote: {e}")
        return 0


async def get_pool_info(wallet: "EvmWallet", pool_address: str) -> PoolInfo | None:
    """Get pool info for a given Uniswap V3 pool address.

    Args:
        wallet: The unified wallet instance.
        pool_address: Uniswap V3 pool address.

    Returns:
        PoolInfo object or None if failed.
    """
    try:
        token0 = await wallet.call_contract(
            contract_address=pool_address,
            abi=UNISWAP_V3_ABI,
            function_name="token0",
            args=[],
        )
        token1 = await wallet.call_contract(
            contract_address=pool_address,
            abi=UNISWAP_V3_ABI,
            function_name="token1",
            args=[],
        )
        fee = await wallet.call_contract(
            contract_address=pool_address,
            abi=UNISWAP_V3_ABI,
            function_name="fee",
            args=[],
        )
        liquidity = await wallet.call_contract(
            contract_address=pool_address,
            abi=UNISWAP_V3_ABI,
            function_name="liquidity",
            args=[],
        )
        slot0 = await wallet.call_contract(
            contract_address=pool_address,
            abi=UNISWAP_V3_ABI,
            function_name="slot0",
            args=[],
        )

        # Get balances
        balance0 = await wallet.call_contract(
            contract_address=token0,
            abi=WOW_ABI,
            function_name="balanceOf",
            args=[pool_address],
        )
        balance1 = await wallet.call_contract(
            contract_address=token1,
            abi=WOW_ABI,
            function_name="balanceOf",
            args=[pool_address],
        )

        return PoolInfo(
            token0=str(token0),
            balance0=int(balance0),
            token1=str(token1),
            balance1=int(balance1),
            fee=int(fee),
            liquidity=int(liquidity),
            sqrt_price_x96=int(slot0[0])
            if isinstance(slot0, (list, tuple))
            else int(slot0),
        )
    except Exception as e:
        logger.warning(f"Failed to fetch pool information: {e}")
        return None


async def exact_input_single(
    wallet: "EvmWallet",
    token_in: str,
    token_out: str,
    amount_in: int,
    fee: int,
) -> int:
    """Get exact input quote from Uniswap.

    Args:
        wallet: The unified wallet instance.
        token_in: Token address to swap from.
        token_out: Token address to swap to.
        amount_in: Amount of tokens to swap (in wei).
        fee: Uniswap pool fee.

    Returns:
        Amount of tokens to receive (in wei).
    """
    try:
        network = get_network_from_chain_id(wallet.chain_id)
        if network not in ADDRESSES:
            raise ValueError(f"Unsupported network: {network}")

        quoter_address = ADDRESSES[network]["uniswap_quoter"]

        result = await wallet.call_contract(
            contract_address=quoter_address,
            abi=UNISWAP_QUOTER_ABI,
            function_name="quoteExactInputSingle",
            args=[
                {
                    "tokenIn": Web3.to_checksum_address(token_in),
                    "tokenOut": Web3.to_checksum_address(token_out),
                    "fee": fee,
                    "amountIn": amount_in,
                    "sqrtPriceLimitX96": 0,
                }
            ],
        )

        # Result is a tuple: (amountOut, sqrtPriceX96After, initializedTicksCrossed, gasEstimate)
        if isinstance(result, (list, tuple)):
            return int(result[0])
        return int(result)
    except Exception as e:
        logger.warning(f"Quoter error: {e}")
        return 0


async def get_uniswap_quote(
    wallet: "EvmWallet",
    token_address: str,
    amount: int,
    quote_type: Literal["buy", "sell"],
) -> Quote:
    """Get Uniswap quote for buying or selling tokens.

    Args:
        wallet: The unified wallet instance.
        token_address: Token address.
        amount: Amount of tokens (in wei).
        quote_type: 'buy' or 'sell'.

    Returns:
        Quote object containing the quote details.
    """
    network = get_network_from_chain_id(wallet.chain_id)
    if network not in ADDRESSES:
        return Quote(
            amount_in=amount,
            amount_out=0,
            fee=None,
            error=f"Unsupported network: {network}",
        )

    # Get pool address from token
    try:
        pool_address = await wallet.call_contract(
            contract_address=token_address,
            abi=WOW_ABI,
            function_name="poolAddress",
            args=[],
        )
    except Exception as e:
        return Quote(
            amount_in=amount,
            amount_out=0,
            fee=None,
            error=f"Failed to get pool address: {e}",
        )

    if not pool_address:
        return Quote(
            amount_in=amount,
            amount_out=0,
            fee=None,
            error="Invalid pool address",
        )

    # Get pool info
    pool_info = await get_pool_info(wallet, str(pool_address))
    if not pool_info:
        return Quote(
            amount_in=amount,
            amount_out=0,
            fee=None,
            error="Failed to fetch pool information",
        )

    weth_address = ADDRESSES[network]["weth"]
    is_token0_weth = pool_info.token0.lower() == weth_address.lower()

    # Determine token_in and token_out based on quote type
    if quote_type == "buy":
        # Buying tokens with ETH
        token_in = pool_info.token0 if is_token0_weth else pool_info.token1
        token_out = pool_info.token1 if is_token0_weth else pool_info.token0
    else:
        # Selling tokens for ETH
        token_in = pool_info.token1 if is_token0_weth else pool_info.token0
        token_out = pool_info.token0 if is_token0_weth else pool_info.token1

    # Get quote
    amount_out = await exact_input_single(
        wallet, token_in, token_out, amount, pool_info.fee
    )

    if amount_out == 0:
        return Quote(
            amount_in=amount,
            amount_out=0,
            fee=pool_info.fee / 1000000 if pool_info.fee else None,
            error="Failed to fetch quote or insufficient liquidity",
        )

    return Quote(
        amount_in=amount,
        amount_out=amount_out,
        fee=pool_info.fee / 1000000 if pool_info.fee else None,
        error=None,
    )


async def get_token_balance(
    wallet: "EvmWallet",
    token_address: str,
    holder_address: str | None = None,
) -> int:
    """Get token balance for an address.

    Args:
        wallet: The unified wallet instance.
        token_address: Token contract address.
        holder_address: Address to check balance for (defaults to wallet address).

    Returns:
        Token balance in wei.
    """
    if holder_address is None:
        holder_address = wallet.address

    try:
        balance = await wallet.call_contract(
            contract_address=token_address,
            abi=WOW_ABI,
            function_name="balanceOf",
            args=[Web3.to_checksum_address(holder_address)],
        )
        return int(balance)
    except Exception as e:
        logger.warning(f"Error getting token balance: {e}")
        return 0
