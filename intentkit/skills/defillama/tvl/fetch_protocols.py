"""Tool for fetching all protocols via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_protocols
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PROTOCOLS_PROMPT = (
    """Fetch all DeFi protocols tracked by DefiLlama with TVL, chain, and metadata."""
)


class Hallmark(BaseModel):
    """Model representing a protocol hallmark (significant event)."""

    timestamp: int
    description: str


class Protocol(BaseModel):
    """Model representing a DeFi protocol."""

    id: str = Field(..., description="ID")
    name: str = Field(..., description="Name")
    address: str | None = Field(None, description="Contract address")
    symbol: str = Field(..., description="Token symbol")
    url: str | None = Field(None, description="Website")
    description: str | None = Field(None, description="Description")
    chain: str | None = Field(None, description="Main chain")
    logo: str | None = Field(None, description="Logo URL")
    audits: str | int = Field("0", description="Audit count")
    audit_note: str | None = Field(None, description="Audit note")
    audit_links: list[str] | None = Field(None, description="Audit links")
    gecko_id: str | None = Field(None, description="CoinGecko ID")
    cmcId: str | int | None = Field(None, description="CMC ID")
    category: str = Field(..., description="Category")
    chains: list[str] = Field(default_factory=list, description="Chains")
    module: str = Field(..., description="Module")
    parentProtocol: str | None = Field(None, description="Parent protocol")
    twitter: str | None = Field(None, description="Twitter")
    github: list[str] | None = Field(None, description="GitHub orgs")
    oracles: list[str] = Field(default_factory=list, description="Oracles used")
    forkedFrom: list[str] = Field(default_factory=list, description="Forked from")
    methodology: str | None = Field(None, description="TVL methodology")
    listedAt: int | None = Field(None, description="Listed timestamp")
    openSource: bool | None = Field(None, description="Open source")
    treasury: str | None = Field(None, description="Treasury")
    misrepresentedTokens: bool | None = Field(None, description="Misrepresented tokens")
    hallmarks: list[Hallmark] | None = Field(None, description="Key events")
    tvl: float | None = Field(None, description="TVL in USD")
    chainTvls: dict[str, float] = Field(
        default_factory=dict, description="TVL by chain"
    )
    change_1h: float | None = Field(None, description="1h change %")
    change_1d: float | None = Field(None, description="1d change %")
    change_7d: float | None = Field(None, description="7d change %")
    staking: float | None = Field(None, description="Staking value")
    pool2: float | None = Field(None, description="Pool2 value")
    borrowed: float | None = Field(None, description="Borrowed value")
    tokenBreakdowns: dict[str, float] = Field(
        default_factory=dict, description="TVL by token"
    )
    mcap: float | None = Field(None, description="Market cap")


class DefiLlamaProtocolsOutput(BaseModel):
    """Output model for the protocols fetching tool."""

    protocols: list[Protocol] = Field(default_factory=list, description="Protocols")
    error: str | None = Field(None, description="Error message")


class DefiLlamaFetchProtocols(DefiLlamaBaseTool):
    """Tool for fetching all protocols from DeFi Llama.

    This tool retrieves information about all protocols tracked by DeFi Llama,
    including their TVL, supported chains, and related metrics.

    Example:
        protocols_tool = DefiLlamaFetchProtocols(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await protocols_tool._arun()
    """

    name: str = "defillama_fetch_protocols"
    description: str = FETCH_PROTOCOLS_PROMPT

    class EmptyArgsSchema(BaseModel):
        """Empty schema for no input parameters."""

        pass

    args_schema: ArgsSchema | None = EmptyArgsSchema

    async def _arun(self, **kwargs) -> DefiLlamaProtocolsOutput:
        """Fetch information about all protocols.

        Returns:
            DefiLlamaProtocolsOutput containing list of protocols or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return DefiLlamaProtocolsOutput(error=error_msg)

            # Fetch protocols from API
            result = await fetch_protocols()

            if isinstance(result, dict) and "error" in result:
                return DefiLlamaProtocolsOutput(error=result["error"])

            # Convert raw data to Protocol models
            protocols = []
            for protocol_data in result:
                try:
                    # Process hallmarks if present
                    hallmarks = None
                    if "hallmarks" in protocol_data and protocol_data["hallmarks"]:
                        hallmarks = [
                            Hallmark(timestamp=h[0], description=h[1])
                            for h in protocol_data["hallmarks"]
                        ]

                    # Create protocol model
                    protocol = Protocol(
                        **{k: v for k, v in protocol_data.items() if k != "hallmarks"},
                        hallmarks=hallmarks,
                    )
                    protocols.append(protocol)
                except Exception as e:
                    # Log error for individual protocol processing but continue with others
                    print(
                        f"Error processing protocol {protocol_data.get('name', 'unknown')}: {str(e)}"
                    )
                    continue

            return DefiLlamaProtocolsOutput(protocols=protocols)

        except Exception as e:
            return DefiLlamaProtocolsOutput(error=str(e))
