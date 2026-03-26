"""Tool for fetching specific protocol details via DeFi Llama API."""

from typing import Any

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_protocol
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PROTOCOL_PROMPT = """Fetch detailed protocol info from DefiLlama including TVL, tokens, chains, and metadata. Provide protocol slug (e.g. 'aave')."""


class TokenAmount(BaseModel):
    """Model representing token amounts at a specific date."""

    date: int = Field(..., description="Timestamp")
    tokens: dict[str, float] = Field(..., description="Token amounts by symbol")


class ChainTVLData(BaseModel):
    """Model representing TVL data for a specific chain."""

    tvl: list[dict[str, float]] = Field(..., description="TVL history")
    tokens: dict[str, float] | None = Field(None, description="Token amounts")
    tokensInUsd: dict[str, float] | None = Field(None, description="Token amounts USD")


class HistoricalTVL(BaseModel):
    """Model representing a historical TVL data point."""

    date: int = Field(..., description="Timestamp")
    totalLiquidityUSD: float = Field(..., description="TVL in USD")


class Raise(BaseModel):
    """Model representing a funding round."""

    date: int = Field(..., description="Date")
    name: str = Field(..., description="Name")
    round: str = Field(..., description="Round type")
    amount: float = Field(..., description="Amount raised (M)")
    chains: list[str] = Field(..., description="Chains")
    sector: str = Field(..., description="Sector")
    category: str = Field(..., description="Category")
    categoryGroup: str = Field(..., description="Category group")
    source: str = Field(..., description="Source")
    leadInvestors: list[str] = Field(default_factory=list, description="Lead investors")
    otherInvestors: list[str] = Field(
        default_factory=list, description="Other investors"
    )
    valuation: float | None = Field(None, description="Valuation")
    defillamaId: str | None = Field(None, description="DefiLlama ID")


class Hallmark(BaseModel):
    """Model representing a significant protocol event."""

    timestamp: int
    description: str


class ProtocolDetail(BaseModel):
    """Model representing detailed protocol information."""

    id: str = Field(..., description="ID")
    name: str = Field(..., description="Name")
    address: str | None = Field(None, description="Address")
    symbol: str = Field(..., description="Token symbol")
    url: str = Field(..., description="Website")
    description: str = Field(..., description="Description")
    logo: str = Field(..., description="Logo URL")
    chains: list[str] = Field(default_factory=list, description="Chains")
    currentChainTvls: dict[str, float] = Field(..., description="TVL by chain")
    chainTvls: dict[str, ChainTVLData] = Field(..., description="TVL history by chain")
    gecko_id: str | None = Field(None, description="CoinGecko ID")
    cmcId: str | None = Field(None, description="CMC ID")
    twitter: str | None = Field(None, description="Twitter")
    treasury: str | None = Field(None, description="Treasury")
    governanceID: list[str] | None = Field(None, description="Governance IDs")
    github: list[str] | None = Field(None, description="GitHub repos")
    isParentProtocol: bool | None = Field(None, description="Is parent protocol")
    otherProtocols: list[str] | None = Field(None, description="Related protocols")
    tokens: list[TokenAmount] = Field(default_factory=list, description="Token history")
    tvl: list[HistoricalTVL] = Field(..., description="TVL history")
    raises: list[Raise] | None = Field(None, description="Funding rounds")
    hallmarks: list[Hallmark] | None = Field(None, description="Key events")
    mcap: float | None = Field(None, description="Market cap")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Metrics")


class DefiLlamaProtocolInput(BaseModel):
    """Input model for fetching protocol details."""

    protocol: str = Field(..., description="Protocol slug (e.g. 'aave')")


class DefiLlamaProtocolOutput(BaseModel):
    """Output model for the protocol fetching tool."""

    protocol: ProtocolDetail | None = Field(None, description="Protocol data")
    error: str | None = Field(default=None, description="Error message")


class DefiLlamaFetchProtocol(DefiLlamaBaseTool):
    """Tool for fetching detailed protocol information from DeFi Llama.

    This tool retrieves comprehensive information about a specific protocol,
    including TVL history, token breakdowns, and metadata.

    Example:
        protocol_tool = DefiLlamaFetchProtocol(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await protocol_tool._arun(protocol="aave")
    """

    name: str = "defillama_fetch_protocol"
    description: str = FETCH_PROTOCOL_PROMPT
    args_schema: ArgsSchema | None = DefiLlamaProtocolInput

    async def _arun(self, protocol: str) -> DefiLlamaProtocolOutput:
        """Fetch detailed information about a specific protocol.

        Args:
            config: Runnable configuration
            protocol: Protocol identifier to fetch

        Returns:
            DefiLlamaProtocolOutput containing protocol details or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch protocol data from API
        result = await fetch_protocol(protocol)

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
