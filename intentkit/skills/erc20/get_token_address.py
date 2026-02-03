"""ERC20 get_token_address skill."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.erc20.base import ERC20BaseTool
from intentkit.skills.erc20.utils import (
    get_available_token_symbols,
    get_token_address_by_symbol,
)


class GetTokenAddressInput(BaseModel):
    """Input schema for ERC20 get_token_address."""

    symbol: str = Field(
        ...,
        description="The token symbol (e.g. USDC, EURC, CBBTC, WETH)",
    )


class ERC20GetTokenAddress(ERC20BaseTool):
    """Get the contract address for a token symbol on the current network.

    This tool returns the contract address for frequently used ERC20 tokens
    based on their symbol and the agent's configured network.
    """

    name: str = "erc20_get_token_address"
    description: str = """Get the contract address for frequently used ERC20 tokens on different networks.

Inputs:
- symbol: The token symbol (e.g. USDC, EURC, CBBTC, WETH)

Returns the contract address for the token on the current network.
If the token is not found, returns available token symbols for the network.

Supported tokens vary by network:
- base-mainnet: USDC, EURC, CBBTC, CBETH, WETH, ZORA, AERO, BNKR, CLANKER
- base-sepolia: USDC, EURC, CBBTC, WETH
- ethereum-mainnet: USDC, EURC, CBBTC, WETH, CBETH
- polygon-mainnet: USDC
- arbitrum-mainnet: USDC, WETH
- optimism-mainnet: USDC, WETH
"""
    args_schema: ArgsSchema | None = GetTokenAddressInput

    async def _arun(
        self,
        symbol: str,
    ) -> str:
        """Get the contract address for a token symbol on the current network.

        Args:
            symbol: The token symbol to look up.

        Returns:
            A message containing the token address or error details.
        """
        try:
            # Get the network ID from the agent context
            network_id = self.get_agent_network_id()

            if not network_id:
                return "Error: Agent network is not configured. Please set the network_id in the agent configuration."

            # Look up the token address
            token_address = get_token_address_by_symbol(network_id, symbol)

            if token_address:
                return f"Token address for {symbol.upper()} on {network_id}: {token_address}"

            # Token not found - provide helpful error message
            available_symbols = get_available_token_symbols(network_id)

            if available_symbols:
                available_text = ", ".join(available_symbols)
                return (
                    f'Error: Token symbol "{symbol}" not found on {network_id}. '
                    f"Available token symbols: {available_text}"
                )
            else:
                return (
                    f'Error: Token symbol "{symbol}" not found. '
                    f"No token symbols are configured for network {network_id}."
                )

        except Exception as e:
            return f"Error getting token address: {e!s}"
