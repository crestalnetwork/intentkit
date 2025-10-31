"""Tool for fetching all protocols via DeFi Llama API."""

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_protocols
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PROTOCOLS_PROMPT = """
This tool fetches information about all protocols tracked by DeFi Llama.
No input parameters are required. Returns comprehensive data for each protocol including:
- Basic information (name, description, website, logo)
- TVL metrics (total and per-chain breakdowns)
- Audit status and security information
- Token details and market metrics
- Chain support and deployment information
- Social media and development links
- Protocol relationships (forks, oracles)
- Historical events and significant updates
Returns the complete list of protocols or an error if the request fails.
"""


class Hallmark(BaseModel):
    """Model representing a protocol hallmark (significant event)."""

    timestamp: int
    description: str


class Protocol(BaseModel):
    """Model representing a DeFi protocol."""

    # Basic Info
    id: str = Field(..., description="Protocol unique identifier")
    name: str = Field(..., description="Protocol name")
    address: str | None = Field(None, description="Protocol's main contract address")
    symbol: str = Field(..., description="Protocol token symbol")
    url: str | None = Field(None, description="Protocol website")
    description: str | None = Field(None, description="Protocol description")
    chain: str | None = Field(None, description="Main chain of the protocol")
    logo: str | None = Field(None, description="URL to protocol logo")

    # Audit Information
    audits: str | int = Field("0", description="Number of audits")
    audit_note: str | None = Field(None, description="Additional audit information")
    audit_links: list[str] | None = Field(None, description="Links to audit reports")

    # External IDs
    gecko_id: str | None = Field(None, description="CoinGecko ID")
    cmcId: str | int | None = Field(None, description="CoinMarketCap ID")

    # Classification
    category: str = Field(..., description="Protocol category")
    chains: list[str] = Field(
        default_factory=list, description="Chains the protocol operates on"
    )

    # Module and Related Info
    module: str = Field(..., description="Module name in DefiLlama")
    parentProtocol: str | None = Field(None, description="Parent protocol identifier")

    # Social and Development
    twitter: str | None = Field(None, description="Twitter handle")
    github: list[str] | None = Field(None, description="GitHub organization names")

    # Protocol Relationships
    oracles: list[str] = Field(default_factory=list, description="Oracle services used")
    forkedFrom: list[str] = Field(
        default_factory=list, description="Protocols this one was forked from"
    )

    # Additional Metadata
    methodology: str | None = Field(None, description="TVL calculation methodology")
    listedAt: int | None = Field(None, description="Timestamp when protocol was listed")
    openSource: bool | None = Field(None, description="Whether protocol is open source")
    treasury: str | None = Field(None, description="Treasury information")
    misrepresentedTokens: bool | None = Field(
        None, description="Whether tokens are misrepresented"
    )
    hallmarks: list[Hallmark] | None = Field(
        None, description="Significant protocol events"
    )

    # TVL Related Data
    tvl: float | None = Field(None, description="Total Value Locked in USD")
    chainTvls: dict[str, float] = Field(
        default_factory=dict,
        description="TVL breakdown by chain including special types (staking, borrowed, etc.)",
    )
    change_1h: float | None = Field(None, description="1 hour TVL change percentage")
    change_1d: float | None = Field(None, description="1 day TVL change percentage")
    change_7d: float | None = Field(None, description="7 day TVL change percentage")

    # Additional TVL Components
    staking: float | None = Field(None, description="Value in staking")
    pool2: float | None = Field(None, description="Value in pool2")
    borrowed: float | None = Field(None, description="Value borrowed")

    # Token Information
    tokenBreakdowns: dict[str, float] = Field(
        default_factory=dict, description="TVL breakdown by token"
    )
    mcap: float | None = Field(None, description="Market capitalization")


class DefiLlamaProtocolsOutput(BaseModel):
    """Output model for the protocols fetching tool."""

    protocols: list[Protocol] = Field(
        default_factory=list, description="List of fetched protocols"
    )
    error: str | None = Field(None, description="Error message if any")


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

    args_schema: type[BaseModel] = EmptyArgsSchema

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
