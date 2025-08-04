"""Tool for fetching specific protocol details via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_protocol
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PROTOCOL_PROMPT = """
This tool fetches comprehensive details about a specific DeFi protocol.
Provide the protocol identifier (e.g., "aave", "curve") to get detailed information including:
- Basic protocol information (name, description, website)
- TVL data across different chains
- Token information and historical amounts
- Social media and development links
- Funding history and significant events
- Market metrics and related protocols
Returns complete protocol details or an error if the protocol is not found.
"""


class TokenAmount(BaseModel):
    """Model representing token amounts at a specific date."""

    date: int = Field(..., description="Unix timestamp")
    tokens: Dict[str, float] = Field(..., description="Token amounts keyed by symbol")


class ChainTVLData(BaseModel):
    """Model representing TVL data for a specific chain."""

    tvl: List[Dict[str, float]] = Field(..., description="Historical TVL data points")
    tokens: Optional[Dict[str, float]] = Field(
        None, description="Current token amounts"
    )
    tokensInUsd: Optional[Dict[str, float]] = Field(
        None, description="Current token amounts in USD"
    )


class HistoricalTVL(BaseModel):
    """Model representing a historical TVL data point."""

    date: int = Field(..., description="Unix timestamp")
    totalLiquidityUSD: float = Field(..., description="Total TVL in USD")


class Raise(BaseModel):
    """Model representing a funding round."""

    date: int = Field(..., description="Funding date")
    name: str = Field(..., description="Protocol name")
    round: str = Field(..., description="Funding round type")
    amount: float = Field(..., description="Amount raised in millions")
    chains: List[str] = Field(..., description="Chains involved")
    sector: str = Field(..., description="Business sector")
    category: str = Field(..., description="Protocol category")
    categoryGroup: str = Field(..., description="Category group")
    source: str = Field(..., description="Information source")
    leadInvestors: List[str] = Field(default_factory=list, description="Lead investors")
    otherInvestors: List[str] = Field(
        default_factory=list, description="Other investors"
    )
    valuation: Optional[float] = Field(None, description="Valuation at time of raise")
    defillamaId: Optional[str] = Field(None, description="DefiLlama ID")


class Hallmark(BaseModel):
    """Model representing a significant protocol event."""

    timestamp: int
    description: str


class ProtocolDetail(BaseModel):
    """Model representing detailed protocol information."""

    # Basic Info
    id: str = Field(..., description="Protocol unique identifier")
    name: str = Field(..., description="Protocol name")
    address: Optional[str] = Field(None, description="Protocol address")
    symbol: str = Field(..., description="Protocol token symbol")
    url: str = Field(..., description="Protocol website")
    description: str = Field(..., description="Protocol description")
    logo: str = Field(..., description="Logo URL")

    # Chain Info
    chains: List[str] = Field(default_factory=list, description="Supported chains")
    currentChainTvls: Dict[str, float] = Field(..., description="Current TVL by chain")
    chainTvls: Dict[str, ChainTVLData] = Field(
        ..., description="Historical TVL data by chain"
    )

    # Identifiers
    gecko_id: Optional[str] = Field(None, description="CoinGecko ID")
    cmcId: Optional[str] = Field(None, description="CoinMarketCap ID")

    # Social & Development
    twitter: Optional[str] = Field(None, description="Twitter handle")
    treasury: Optional[str] = Field(None, description="Treasury information")
    governanceID: Optional[List[str]] = Field(
        None, description="Governance identifiers"
    )
    github: Optional[List[str]] = Field(None, description="GitHub repositories")

    # Protocol Relationships
    isParentProtocol: Optional[bool] = Field(
        None, description="Whether this is a parent protocol"
    )
    otherProtocols: Optional[List[str]] = Field(None, description="Related protocols")

    # Historical Data
    tokens: List[TokenAmount] = Field(
        default_factory=list, description="Historical token amounts"
    )
    tvl: List[HistoricalTVL] = Field(..., description="Historical TVL data points")
    raises: Optional[List[Raise]] = Field(None, description="Funding rounds")
    hallmarks: Optional[List[Hallmark]] = Field(None, description="Significant events")

    # Market Data
    mcap: Optional[float] = Field(None, description="Market capitalization")
    metrics: Dict = Field(default_factory=dict, description="Additional metrics")


class DefiLlamaProtocolInput(BaseModel):
    """Input model for fetching protocol details."""

    protocol: str = Field(..., description="Protocol identifier to fetch")


class DefiLlamaProtocolOutput(BaseModel):
    """Output model for the protocol fetching tool."""

    protocol: Optional[ProtocolDetail] = Field(None, description="Protocol details")
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchProtocol(DefiLlamaBaseTool):
    """Tool for fetching detailed protocol information from DeFi Llama.

    This tool retrieves comprehensive information about a specific protocol,
    including TVL history, token breakdowns, and metadata.

    Example:
        protocol_tool = DefiLlamaFetchProtocol(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await protocol_tool._arun(protocol="aave")
    """

    name: str = "defillama_fetch_protocol"
    description: str = FETCH_PROTOCOL_PROMPT
    args_schema: Type[BaseModel] = DefiLlamaProtocolInput

    async def _arun(self, protocol: str) -> DefiLlamaProtocolOutput:
        """Fetch detailed information about a specific protocol.

        Args:
            config: Runnable configuration
            protocol: Protocol identifier to fetch

        Returns:
            DefiLlamaProtocolOutput containing protocol details or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return DefiLlamaProtocolOutput(error=error_msg)

            # Fetch protocol data from API
            result = await fetch_protocol(protocol)

            if isinstance(result, dict) and "error" in result:
                return DefiLlamaProtocolOutput(error=result["error"])

            # Process hallmarks if present
            hallmarks = None
            if "hallmarks" in result:
                hallmarks = [
                    Hallmark(timestamp=h[0], description=h[1])
                    for h in result.get("hallmarks", [])
                ]

            # Create raises objects if present
            raises = None
            if "raises" in result:
                raises = [Raise(**r) for r in result.get("raises", [])]

            # Create protocol detail object
            protocol_detail = ProtocolDetail(
                **{k: v for k, v in result.items() if k not in ["hallmarks", "raises"]},
                hallmarks=hallmarks,
                raises=raises,
            )

            return DefiLlamaProtocolOutput(protocol=protocol_detail)

        except Exception as e:
            return DefiLlamaProtocolOutput(error=str(e))
