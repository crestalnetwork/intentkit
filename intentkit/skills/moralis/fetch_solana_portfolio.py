"""fetching Solana wallet portfolio."""

import logging
from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.moralis.api import (
    get_solana_balance,
    get_solana_nfts,
    get_solana_portfolio,
    get_solana_spl_tokens,
    get_token_price,
)
from intentkit.skills.moralis.base import WalletBaseTool

logger = logging.getLogger(__name__)


class SolanaPortfolioInput(BaseModel):
    """Input for FetchSolanaPortfolio tool."""

    address: str = Field(..., description="Solana wallet address")
    network: str = Field(
        default="mainnet", description="Solana network to use (mainnet or devnet)"
    )
    include_nfts: bool = Field(
        default=False, description="Whether to include NFTs in the response"
    )
    include_price_data: bool = Field(
        default=True, description="Whether to include price data for tokens"
    )


class SolanaTokenInfo(BaseModel):
    """Model for Solana token information."""

    symbol: str
    name: str
    decimals: int
    mint: str
    associated_token_address: str


class SolanaTokenBalance(BaseModel):
    """Model for Solana token balance."""

    token_info: SolanaTokenInfo
    amount: float
    amount_raw: str
    usd_value: Optional[float] = 0.0


class SolanaNftInfo(BaseModel):
    """Model for Solana NFT information."""

    mint: str
    name: Optional[str] = None
    symbol: Optional[str] = None
    associated_token_address: str
    metadata: Optional[Dict] = None


class SolanaPortfolioOutput(BaseModel):
    """Output for FetchSolanaPortfolio tool."""

    address: str
    sol_balance: float
    sol_balance_lamports: int
    sol_price_usd: Optional[float] = None
    sol_value_usd: Optional[float] = None
    tokens: List[SolanaTokenBalance] = []
    nfts: List[SolanaNftInfo] = []
    total_value_usd: float = 0.0
    error: Optional[str] = None


class FetchSolanaPortfolio(WalletBaseTool):
    """Tool for fetching Solana wallet portfolio.

    This tool retrieves detailed information about a Solana wallet's holdings,
    including native SOL, SPL tokens, and optionally NFTs.
    """

    name: str = "moralis_fetch_solana_portfolio"
    description: str = (
        "Get comprehensive portfolio data for a Solana wallet including:\n"
        "- Native SOL balance\n"
        "- SPL token balances\n"
        "- NFT holdings (optional)\n"
        "- USD values of assets\n"
        "Use this tool whenever the user asks specifically about Solana holdings."
    )
    args_schema: Type[BaseModel] = SolanaPortfolioInput

    async def _arun(
        self,
        address: str,
        network: str = "mainnet",
        include_nfts: bool = False,
        include_price_data: bool = True,
        **kwargs,
    ) -> SolanaPortfolioOutput:
        """Fetch Solana wallet portfolio data.

        Args:
            address: Solana wallet address
            network: Solana network to use (mainnet or devnet)
            include_nfts: Whether to include NFTs in the response
            include_price_data: Whether to include price data for tokens

        Returns:
            SolanaPortfolioOutput containing the Solana wallet's portfolio data
        """
        try:
            # Try to get complete portfolio
            sol_portfolio = await get_solana_portfolio(self.api_key, address, network)

            if "error" not in sol_portfolio:
                return await self._process_portfolio_data(
                    address, network, sol_portfolio, include_nfts, include_price_data
                )
            else:
                # If portfolio endpoint fails, try to fetch data separately
                return await self._fetch_separate_portfolio_data(
                    address, network, include_nfts, include_price_data
                )

        except Exception as e:
            logger.error(f"Error fetching Solana portfolio: {str(e)}")
            return SolanaPortfolioOutput(
                address=address, sol_balance=0, sol_balance_lamports=0, error=str(e)
            )

    async def _process_portfolio_data(
        self,
        address: str,
        network: str,
        sol_portfolio: Dict,
        include_nfts: bool,
        include_price_data: bool,
    ) -> SolanaPortfolioOutput:
        """Process portfolio data from the API.

        Args:
            address: Solana wallet address
            network: Solana network
            sol_portfolio: Portfolio data from the API
            include_nfts: Whether to include NFTs
            include_price_data: Whether to include price data

        Returns:
            SolanaPortfolioOutput with processed data
        """
        result = SolanaPortfolioOutput(
            address=address,
            sol_balance=float(sol_portfolio.get("nativeBalance", {}).get("solana", 0)),
            sol_balance_lamports=int(
                sol_portfolio.get("nativeBalance", {}).get("lamports", 0)
            ),
        )

        # Process tokens
        tokens = []
        for token in sol_portfolio.get("tokens", []):
            token_info = SolanaTokenInfo(
                symbol=token.get("symbol", ""),
                name=token.get("name", ""),
                decimals=int(token.get("decimals", 0)),
                mint=token.get("mint", ""),
                associated_token_address=token.get("associatedTokenAddress", ""),
            )

            token_balance = SolanaTokenBalance(
                token_info=token_info,
                amount=float(token.get("amount", 0)),
                amount_raw=token.get("amountRaw", "0"),
            )

            tokens.append(token_balance)

        result.tokens = tokens

        # Fetch NFTs if requested
        if include_nfts:
            nfts_result = await get_solana_nfts(self.api_key, address, network)

            if "error" not in nfts_result and isinstance(nfts_result, list):
                nfts = []
                for nft in nfts_result:
                    nft_info = SolanaNftInfo(
                        mint=nft.get("mint", ""),
                        name=nft.get("name"),
                        symbol=nft.get("symbol"),
                        associated_token_address=nft.get("associatedTokenAddress", ""),
                        metadata=nft.get("metadata"),
                    )
                    nfts.append(nft_info)

                result.nfts = nfts

        # Fetch price data if requested
        if include_price_data:
            # Fetch SOL price
            sol_price_result = await get_token_price(
                self.api_key,
                "So11111111111111111111111111111111111111112",  # SOL mint address
                network,
            )

            if "error" not in sol_price_result:
                sol_price_usd = float(sol_price_result.get("usdPrice", 0))
                result.sol_price_usd = sol_price_usd
                result.sol_value_usd = sol_price_usd * result.sol_balance
                result.total_value_usd += result.sol_value_usd or 0

            # Fetch token prices
            for token in result.tokens:
                if token.token_info.mint:
                    price_result = await get_token_price(
                        self.api_key, token.token_info.mint, network
                    )

                    if "error" not in price_result:
                        token_price_usd = float(price_result.get("usdPrice", 0))
                        token.usd_value = token_price_usd * token.amount
                        result.total_value_usd += token.usd_value

        return result

    async def _fetch_separate_portfolio_data(
        self, address: str, network: str, include_nfts: bool, include_price_data: bool
    ) -> SolanaPortfolioOutput:
        """Fetch portfolio data using separate API calls.

        Args:
            address: Solana wallet address
            network: Solana network
            include_nfts: Whether to include NFTs
            include_price_data: Whether to include price data

        Returns:
            SolanaPortfolioOutput with processed data
        """
        # Get SOL balance
        balance_result = await get_solana_balance(self.api_key, address, network)

        if "error" in balance_result:
            return SolanaPortfolioOutput(
                address=address,
                sol_balance=0,
                sol_balance_lamports=0,
                error=balance_result["error"],
            )

        result = SolanaPortfolioOutput(
            address=address,
            sol_balance=float(balance_result.get("solana", 0)),
            sol_balance_lamports=int(balance_result.get("lamports", 0)),
        )

        # Get SPL tokens
        tokens_result = await get_solana_spl_tokens(self.api_key, address, network)

        if "error" not in tokens_result and isinstance(tokens_result, list):
            tokens = []
            for token in tokens_result:
                token_info = SolanaTokenInfo(
                    symbol=token.get("symbol", ""),
                    name=token.get("name", ""),
                    decimals=int(token.get("decimals", 0)),
                    mint=token.get("mint", ""),
                    associated_token_address=token.get("associatedTokenAddress", ""),
                )

                token_balance = SolanaTokenBalance(
                    token_info=token_info,
                    amount=float(token.get("amount", 0)),
                    amount_raw=token.get("amountRaw", "0"),
                )

                tokens.append(token_balance)

            result.tokens = tokens

        # Fetch NFTs if requested
        if include_nfts:
            nfts_result = await get_solana_nfts(self.api_key, address, network)

            if "error" not in nfts_result and isinstance(nfts_result, list):
                nfts = []
                for nft in nfts_result:
                    nft_info = SolanaNftInfo(
                        mint=nft.get("mint", ""),
                        name=nft.get("name"),
                        symbol=nft.get("symbol"),
                        associated_token_address=nft.get("associatedTokenAddress", ""),
                        metadata=nft.get("metadata"),
                    )
                    nfts.append(nft_info)

                result.nfts = nfts

        # Fetch price data if requested
        if include_price_data:
            # Fetch SOL price
            sol_price_result = await get_token_price(
                self.api_key,
                "So11111111111111111111111111111111111111112",  # SOL mint address
                network,
            )

            if "error" not in sol_price_result:
                sol_price_usd = float(sol_price_result.get("usdPrice", 0))
                result.sol_price_usd = sol_price_usd
                result.sol_value_usd = sol_price_usd * result.sol_balance
                result.total_value_usd += result.sol_value_usd or 0

            # Fetch token prices
            for token in result.tokens:
                if token.token_info.mint:
                    price_result = await get_token_price(
                        self.api_key, token.token_info.mint, network
                    )

                    if "error" not in price_result:
                        token_price_usd = float(price_result.get("usdPrice", 0))
                        token.usd_value = token_price_usd * token.amount
                        result.total_value_usd += token.usd_value

        return result
