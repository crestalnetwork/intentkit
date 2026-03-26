"""fetching a complete wallet portfolio (EVM + Solana)."""

import logging
from typing import TypedDict

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.moralis.api import (
    fetch_net_worth,
    fetch_wallet_balances,
    get_solana_balance,
    get_solana_portfolio,
    get_solana_spl_tokens,
    get_token_price,
)
from intentkit.skills.moralis.base import CHAIN_MAPPING, WalletBaseTool

logger = logging.getLogger(__name__)


class FetchWalletPortfolioInput(BaseModel):
    """Input for FetchWalletPortfolio tool."""

    address: str = Field(..., description="Wallet address (EVM or Solana).")
    chains: list[int] | None = Field(
        default=None,
        description="EVM chain IDs to check (all if empty).",
    )
    include_solana: bool = Field(default=True, description="Include Solana.")
    solana_network: str = Field(
        default="mainnet", description="Network: mainnet or devnet."
    )


class TokenBalance(BaseModel):
    """Model for token balance."""

    symbol: str
    name: str
    balance: float
    usd_value: float
    chain: str


class PortfolioOutput(BaseModel):
    """Output for FetchWalletPortfolio tool."""

    address: str
    total_net_worth: float
    chains: dict[str, float]
    tokens: list[TokenBalance]
    error: str | None = None


class _PortfolioData(TypedDict):
    """Internal typed dict for accumulating portfolio data."""

    tokens: list[TokenBalance]
    chains: dict[str, float]
    total_net_worth: float


class FetchWalletPortfolio(WalletBaseTool):
    """Tool for fetching a complete wallet portfolio across all chains (EVM + Solana).

    This tool retrieves detailed information about a wallet's holdings across
    multiple blockchains, including token balances, USD values, and a summary
    of the total portfolio value.
    """

    name: str = "moralis_fetch_wallet_portfolio"
    description: str = "Fetch wallet portfolio across EVM chains and Solana, including balances and net worth."
    args_schema: ArgsSchema | None = FetchWalletPortfolioInput

    async def _arun(
        self,
        address: str,
        chains: list[int] | None = None,
        include_solana: bool = True,
        solana_network: str = "mainnet",
        **kwargs,
    ) -> PortfolioOutput:
        """Fetch wallet portfolio data across multiple chains.

        Args:
            address: Wallet address to fetch portfolio for
            chains: List of EVM chain IDs to check (if None, checks all supported chains)
            include_solana: Whether to include Solana in the analysis
            solana_network: Solana network to use (mainnet or devnet)

        Returns:
            PortfolioOutput containing the wallet's portfolio data
        """
        try:
            # Initialize portfolio data
            portfolio: _PortfolioData = {
                "tokens": [],
                "chains": {},
                "total_net_worth": 0.0,
            }

            # Get EVM chain portfolio
            await self._fetch_evm_portfolio(address, chains, portfolio)

            # Get Solana portfolio if requested
            if include_solana:
                await self._fetch_solana_portfolio(address, solana_network, portfolio)

            return PortfolioOutput(
                address=address,
                total_net_worth=portfolio["total_net_worth"],
                chains=portfolio["chains"],
                tokens=portfolio["tokens"],
            )

        except Exception as e:
            logger.error("Error fetching wallet portfolio: %s", e)
            return PortfolioOutput(
                address=address, total_net_worth=0, chains={}, tokens=[], error=str(e)
            )

    async def _fetch_evm_portfolio(
        self, address: str, chains: list[int] | None, portfolio: _PortfolioData
    ) -> None:
        """Fetch portfolio data for EVM chains.

        Args:
            address: Wallet address to fetch portfolio for
            chains: List of EVM chain IDs to check (if None, checks all supported chains)
            portfolio: Portfolio data to update
        """
        # Get chain IDs to query (use all supported chains if not specified)
        chain_ids = chains or list(CHAIN_MAPPING.keys())

        # Get balances for each chain
        for chain_id in chain_ids:
            balance_data = await fetch_wallet_balances(self.api_key, address, chain_id)

            if "error" in balance_data:
                continue

            chain_name = self._get_chain_name(chain_id)
            chain_total = 0

            for token in balance_data.get("result", []):
                if token.get("usd_value"):
                    portfolio["tokens"].append(
                        TokenBalance(
                            symbol=token.get("symbol", "UNKNOWN"),
                            name=token.get("name", "Unknown Token"),
                            balance=float(token.get("balance_formatted", 0)),
                            usd_value=token["usd_value"],
                            chain=chain_name,
                        )
                    )
                    chain_total += token["usd_value"]

            portfolio["chains"][chain_name] = chain_total
            portfolio["total_net_worth"] += chain_total

        # Add net worth data if available
        net_worth = await fetch_net_worth(self.api_key, address)
        if "result" in net_worth:
            portfolio["total_net_worth"] = net_worth["result"].get(
                "total_networth_usd", portfolio["total_net_worth"]
            )

    async def _fetch_solana_portfolio(
        self, address: str, network: str, portfolio: _PortfolioData
    ) -> None:
        """Fetch portfolio data for Solana.

        Args:
            address: Wallet address to fetch portfolio for
            network: Solana network to use (mainnet or devnet)
            portfolio: Portfolio data to update
        """
        chain_name = "solana"
        chain_total = 0

        # Try to get complete portfolio
        sol_portfolio = await get_solana_portfolio(self.api_key, address, network)

        if "error" not in sol_portfolio:
            # Process native SOL balance
            if "nativeBalance" in sol_portfolio:
                sol_balance = float(sol_portfolio["nativeBalance"].get("solana", 0))

                # Get SOL price
                sol_price_result = await get_token_price(
                    self.api_key,
                    "So11111111111111111111111111111111111111112",  # SOL mint address
                    network,
                )

                sol_price_usd = 0
                if "error" not in sol_price_result:
                    sol_price_usd = float(sol_price_result.get("usdPrice", 0))

                sol_value_usd = sol_balance * sol_price_usd
                chain_total += sol_value_usd

                # Add SOL to tokens
                portfolio["tokens"].append(
                    TokenBalance(
                        symbol="SOL",
                        name="Solana",
                        balance=sol_balance,
                        usd_value=sol_value_usd,
                        chain=chain_name,
                    )
                )

            # Process SPL tokens
            for token in sol_portfolio.get("tokens", []):
                t_symbol: str = token.get("symbol", "UNKNOWN")
                t_name: str = token.get("name", "Unknown Token")
                t_balance: float = float(token.get("amount", 0))
                t_usd_value: float = 0.0

                # Try to get token price
                if token.get("mint"):
                    price_result = await get_token_price(
                        self.api_key, token["mint"], network
                    )

                    if "error" not in price_result:
                        token_price_usd = float(price_result.get("usdPrice", 0))
                        t_usd_value = t_balance * token_price_usd
                        chain_total += t_usd_value

                portfolio["tokens"].append(
                    TokenBalance(
                        symbol=t_symbol,
                        name=t_name,
                        balance=t_balance,
                        usd_value=t_usd_value,
                        chain=chain_name,
                    )
                )
        else:
            # If portfolio endpoint fails, try to fetch balance and tokens separately
            sol_balance_result = await get_solana_balance(
                self.api_key, address, network
            )

            if "error" not in sol_balance_result:
                sol_balance = float(sol_balance_result.get("solana", 0))

                # Get SOL price
                sol_price_result = await get_token_price(
                    self.api_key,
                    "So11111111111111111111111111111111111111112",  # SOL mint address
                    network,
                )

                sol_price_usd = 0
                if "error" not in sol_price_result:
                    sol_price_usd = float(sol_price_result.get("usdPrice", 0))

                sol_value_usd = sol_balance * sol_price_usd
                chain_total += sol_value_usd

                # Add SOL to tokens
                portfolio["tokens"].append(
                    TokenBalance(
                        symbol="SOL",
                        name="Solana",
                        balance=sol_balance,
                        usd_value=sol_value_usd,
                        chain=chain_name,
                    )
                )

            # Get SPL tokens
            tokens_result = await get_solana_spl_tokens(self.api_key, address, network)

            if "error" not in tokens_result and isinstance(tokens_result, list):
                for token in tokens_result:
                    t_symbol = str(token.get("symbol", "UNKNOWN"))
                    t_name = str(token.get("name", "Unknown Token"))
                    t_balance = float(token.get("amount", 0))
                    t_usd_value = 0.0

                    # Try to get token price
                    if token.get("mint"):
                        price_result = await get_token_price(
                            self.api_key, token["mint"], network
                        )

                        if "error" not in price_result:
                            token_price_usd = float(price_result.get("usdPrice", 0))
                            t_usd_value = t_balance * token_price_usd
                            chain_total += t_usd_value

                    portfolio["tokens"].append(
                        TokenBalance(
                            symbol=t_symbol,
                            name=t_name,
                            balance=t_balance,
                            usd_value=t_usd_value,
                            chain=chain_name,
                        )
                    )

        # Update chain total and net worth
        portfolio["chains"][chain_name] = chain_total
        portfolio["total_net_worth"] += chain_total
