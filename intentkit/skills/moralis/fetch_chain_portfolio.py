"""fetching wallet portfolio for a specific blockchain."""

import logging
from typing import List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.moralis.api import fetch_token_approvals, fetch_wallet_balances
from intentkit.skills.moralis.base import WalletBaseTool

logger = logging.getLogger(__name__)


class FetchChainPortfolioInput(BaseModel):
    """Input for FetchChainPortfolio tool."""

    address: str = Field(..., description="Wallet address")
    chain_id: int = Field(..., description="Chain ID to fetch portfolio for")
    include_approvals: bool = Field(
        default=False, description="Whether to include token approvals in the response"
    )


class ChainTokenBalance(BaseModel):
    """Model for token balance on a specific chain."""

    contract_address: str = Field(..., description="Token contract address")
    symbol: str = Field(..., description="Token symbol")
    name: str = Field(..., description="Token name")
    logo: Optional[str] = Field(None, description="Token logo URL")
    decimals: int = Field(..., description="Token decimals")
    balance: float = Field(..., description="Token balance")
    balance_raw: str = Field(..., description="Raw token balance")
    balance_usd: float = Field(0.0, description="USD value of token balance")


class TokenApproval(BaseModel):
    """Model for token approval."""

    token_address: str = Field(..., description="Token contract address")
    token_symbol: Optional[str] = Field(None, description="Token symbol")
    token_name: Optional[str] = Field(None, description="Token name")
    spender: str = Field(..., description="Spender address (contract)")
    spender_name: Optional[str] = Field(None, description="Spender name if known")
    allowance: str = Field(..., description="Raw approval amount")
    allowance_formatted: Optional[float] = Field(
        None, description="Formatted approval amount"
    )
    unlimited: bool = Field(False, description="Whether the approval is unlimited")


class ChainPortfolioOutput(BaseModel):
    """Output for FetchChainPortfolio tool."""

    address: str = Field(..., description="Wallet address")
    chain_id: int = Field(..., description="Chain ID")
    chain_name: str = Field(..., description="Chain name")
    native_token: Optional[ChainTokenBalance] = Field(
        None, description="Native token balance"
    )
    tokens: List[ChainTokenBalance] = Field(
        default_factory=list, description="List of token balances"
    )
    total_usd_value: float = Field(0.0, description="Total USD value on this chain")
    approvals: Optional[List[TokenApproval]] = Field(
        None, description="Token approvals if requested"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class FetchChainPortfolio(WalletBaseTool):
    """Tool for fetching wallet portfolio for a specific blockchain.

    This tool retrieves detailed information about a wallet's holdings on a specific
    blockchain, including token balances, USD values, and optionally token approvals.
    """

    name: str = "moralis_fetch_chain_portfolio"
    description: str = (
        "This tool fetches wallet portfolio data for a specific blockchain.\n"
        "Provide a wallet address and chain ID to get detailed information about tokens and their values.\n"
        "Returns:\n"
        "- Token balances for the specified chain\n"
        "- USD value of each token\n"
        "- Total chain value\n"
        "- Token metadata (symbol, name, decimals)\n"
        "- Token approvals (optional)\n"
        "Use this tool whenever a user wants to see their holdings on a specific blockchain."
    )
    args_schema: Type[BaseModel] = FetchChainPortfolioInput

    async def _arun(
        self, address: str, chain_id: int, include_approvals: bool = False, **kwargs
    ) -> ChainPortfolioOutput:
        """Fetch wallet portfolio for a specific chain.

        Args:
            address: Wallet address to fetch portfolio for
            chain_id: Chain ID to fetch portfolio for
            include_approvals: Whether to include token approvals

        Returns:
            ChainPortfolioOutput containing portfolio data for the specified chain
        """
        try:
            # Fetch wallet balances for the specified chain
            balances = await fetch_wallet_balances(self.api_key, address, chain_id)

            if "error" in balances:
                return ChainPortfolioOutput(
                    address=address,
                    chain_id=chain_id,
                    chain_name=self._get_chain_name(chain_id),
                    error=balances["error"],
                )

            # Process the data
            portfolio = {
                "address": address,
                "chain_id": chain_id,
                "chain_name": self._get_chain_name(chain_id),
                "tokens": [],
                "total_usd_value": 0.0,
            }

            for token in balances.get("result", []):
                token_balance = ChainTokenBalance(
                    contract_address=token["token_address"],
                    symbol=token.get("symbol", "UNKNOWN"),
                    name=token.get("name", "Unknown Token"),
                    logo=token.get("logo", None),
                    decimals=token.get("decimals", 18),
                    balance=float(token.get("balance_formatted", 0)),
                    balance_raw=token.get("balance", "0"),
                    balance_usd=float(token.get("usd_value", 0)),
                )

                # Identify native token
                if token.get("native_token", False):
                    portfolio["native_token"] = token_balance
                else:
                    portfolio["tokens"].append(token_balance)

                # Add to total USD value
                portfolio["total_usd_value"] += token_balance.balance_usd

            # Fetch token approvals if requested
            if include_approvals:
                approvals_data = await fetch_token_approvals(
                    self.api_key, address, chain_id
                )

                if "error" not in approvals_data:
                    approvals = []

                    for approval in approvals_data.get("result", []):
                        # Determine if the approval is unlimited (max uint256)
                        allowance = approval.get("allowance", "0")
                        is_unlimited = (
                            allowance
                            == "115792089237316195423570985008687907853269984665640564039457584007913129639935"
                        )

                        # Create approval object
                        token_approval = TokenApproval(
                            token_address=approval.get("token_address", ""),
                            token_symbol=approval.get("token_symbol"),
                            token_name=approval.get("token_name"),
                            spender=approval.get("spender", ""),
                            spender_name=approval.get("spender_name"),
                            allowance=allowance,
                            allowance_formatted=float(
                                approval.get("allowance_formatted", 0)
                            ),
                            unlimited=is_unlimited,
                        )

                        approvals.append(token_approval)

                    portfolio["approvals"] = approvals

            return ChainPortfolioOutput(**portfolio)

        except Exception as e:
            logger.error(f"Error fetching chain portfolio: {str(e)}")
            return ChainPortfolioOutput(
                address=address,
                chain_id=chain_id,
                chain_name=self._get_chain_name(chain_id),
                error=str(e),
            )
