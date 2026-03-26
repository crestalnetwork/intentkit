"""fetching wallet portfolio for a specific blockchain."""

import logging

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.moralis.api import fetch_token_approvals, fetch_wallet_balances
from intentkit.skills.moralis.base import WalletBaseTool

logger = logging.getLogger(__name__)


class FetchChainPortfolioInput(BaseModel):
    """Input for FetchChainPortfolio tool."""

    address: str = Field(..., description="Wallet address.")
    chain_id: int = Field(..., description="Chain ID.")
    include_approvals: bool = Field(
        default=False, description="Include token approvals."
    )


class ChainTokenBalance(BaseModel):
    """Model for token balance on a specific chain."""

    contract_address: str = Field(..., description="Contract address.")
    symbol: str = Field(..., description="Token symbol.")
    name: str = Field(..., description="Token name.")
    logo: str | None = Field(None, description="Logo URL.")
    decimals: int = Field(..., description="Decimals.")
    balance: float = Field(..., description="Balance.")
    balance_raw: str = Field(..., description="Raw balance.")
    balance_usd: float = Field(0.0, description="USD value.")


class TokenApproval(BaseModel):
    """Model for token approval."""

    token_address: str = Field(..., description="Token address.")
    token_symbol: str | None = Field(None, description="Token symbol.")
    token_name: str | None = Field(None, description="Token name.")
    spender: str = Field(..., description="Spender address.")
    spender_name: str | None = Field(None, description="Spender name.")
    allowance: str = Field(..., description="Raw allowance.")
    allowance_formatted: float | None = Field(None, description="Formatted allowance.")
    unlimited: bool = Field(False, description="Unlimited approval.")


class ChainPortfolioOutput(BaseModel):
    """Output for FetchChainPortfolio tool."""

    address: str = Field(..., description="Wallet address.")
    chain_id: int = Field(..., description="Chain ID.")
    chain_name: str = Field(..., description="Chain name.")
    native_token: ChainTokenBalance | None = Field(None, description="Native token.")
    tokens: list[ChainTokenBalance] = Field(
        default_factory=list, description="Token balances."
    )
    total_usd_value: float = Field(0.0, description="Total USD value.")
    approvals: list[TokenApproval] | None = Field(None, description="Token approvals.")
    error: str | None = Field(None, description="Error message.")


class FetchChainPortfolio(WalletBaseTool):
    """Tool for fetching wallet portfolio for a specific blockchain.

    This tool retrieves detailed information about a wallet's holdings on a specific
    blockchain, including token balances, USD values, and optionally token approvals.
    """

    name: str = "moralis_fetch_chain_portfolio"
    description: str = (
        "Fetch wallet token balances and USD values for a specific blockchain."
    )
    args_schema: ArgsSchema | None = FetchChainPortfolioInput

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
        api_key = self.get_api_key()
        chain_name = self._get_chain_name(chain_id)
        try:
            # Fetch wallet balances for the specified chain
            balances = await fetch_wallet_balances(api_key, address, chain_id)

            if "error" in balances:
                return ChainPortfolioOutput(
                    address=address,
                    chain_id=chain_id,
                    chain_name=chain_name,
                    native_token=None,
                    tokens=[],
                    total_usd_value=0.0,
                    approvals=None,
                    error=balances["error"],
                )

            # Process the data
            native_token: ChainTokenBalance | None = None
            tokens: list[ChainTokenBalance] = []
            total_usd_value: float = 0.0

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
                    native_token = token_balance
                else:
                    tokens.append(token_balance)

                # Add to total USD value
                total_usd_value += token_balance.balance_usd

            # Fetch token approvals if requested
            approvals: list[TokenApproval] | None = None
            if include_approvals:
                approvals_data = await fetch_token_approvals(api_key, address, chain_id)

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

            return ChainPortfolioOutput(
                address=address,
                chain_id=chain_id,
                chain_name=chain_name,
                native_token=native_token,
                tokens=tokens,
                total_usd_value=total_usd_value,
                approvals=approvals,
                error=None,
            )

        except Exception as e:
            logger.error("Error fetching chain portfolio: %s", e)
            return ChainPortfolioOutput(
                address=address,
                chain_id=chain_id,
                chain_name=chain_name,
                native_token=None,
                tokens=[],
                total_usd_value=0.0,
                approvals=None,
                error=str(e),
            )
