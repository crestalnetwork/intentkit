from typing import Literal, Type

import httpx
from pydantic import BaseModel, Field

from skills.enso.base import (
    EnsoBaseTool,
    base_url,
    default_chain_id,
    default_protocol_slug,
)

# Actual Enso output types
# class UnderlyingToken(BaseModel):
#     address: str | None = Field(None, description="The address of the token")
#     chainId: int | None = Field(None, description="The blockchain chain ID")
#     type: str | None = Field(None, description="The type of the token (e.g., base token)")
#     decimals: int | None = Field(None, description="The number of decimals for the token")
#     name: str | None = Field(None, description="The name of the token")
#     symbol: str | None = Field(None, description="The symbol of the token")
#     logosUri: list[HttpUrl] | None = Field(None, description="List of URLs to token's logos")
#
#
# class TokenData(BaseModel):
#     chainId: int | None = Field(None, description="The blockchain chain ID")
#     address: str | None = Field(None, description="The address of the token")
#     decimals: int | None = Field(None, description="The number of decimals for the token")
#     name: str | None = Field(None, description="The name of the token")
#     symbol: str | None = Field(None, description="The symbol of the token")
#     logosUri: list[HttpUrl] | None = Field(None, description="List of URLs to token's logos")
#     type: str | None = Field(None, description="The type of the token (e.g., defi, base, etc.)")
#     protocolSlug: str | None = Field(None, description="The protocol slug associated with the token")
#     underlyingTokens: list[UnderlyingToken] | None = Field(None, description="List of underlying tokens")
#     primaryAddress: str | None = Field(None, description="The primary address associated with the token")
#     apy: float | None = Field(None, description="The annual percentage yield (APY) for the token")
#
#
# class MetaData(BaseModel):
#     total: int | None = Field(None, description="Total number of records")
#     lastPage: int | None = Field(None, description="Last page of the data")
#     currentPage: int | None = Field(None, description="Current page of the data")
#     perPage: int | None = Field(None, description="Number of records per page")
#     prev: int | None = Field(None, description="Previous page number, if applicable")
#     next: int | None = Field(None, description="Next page number, if applicable")
#
#
# class TokenResponse(BaseModel):
#     data: list[TokenData] | None = Field(None, description="List of token data")
#     meta: MetaData | None = Field(None, description="Metadata regarding pagination")


class UnderlyingTokenCompact(BaseModel):
    address: str | None = Field(None, description="The address of the token")
    type: str | None = Field(
        None, description="The type of the token (e.g., base token)"
    )
    name: str | None = Field(None, description="The name of the token")
    symbol: str | None = Field(None, description="The symbol of the token")


class TokenResponseCompact(BaseModel):
    name: str | None = Field(None, description="The name of the token")
    symbol: str | None = Field(None, description="The symbol of the token")
    address: str | None = Field(None, description="The address of the token")
    primaryAddress: str | None = Field(
        None, description="The primary address associated with the token"
    )
    type: str | None = Field(
        None, description="The type of the token (e.g., defi, base, etc.)"
    )
    apy: float | None = Field(
        None, description="The annual percentage yield (APY) for the token"
    )
    underlyingTokens: list[UnderlyingTokenCompact] | None = Field(
        None, description="List of underlying tokens"
    )
    decimals: int | None = Field(
        None, description="The number of decimals for the token"
    )


class EnsoGetTokensInput(BaseModel):
    chainId: int = Field(
        default_chain_id,
        description="The blockchain chain ID",
    )
    protocolSlug: str = Field(
        default_protocol_slug,
        description="The protocol slug (e.g., 'aave-v2', 'aave-v3', 'compound-v2')",
    )
    underlyingTokens: str | list[str] | None = Field(
        None,
        description="Underlying tokens (e.g. 0xdAC17F958D2ee523a2206206994597C13D831ec7)",
    )
    primaryAddress: str | None = Field(
        None,
        description="Ethereum address for contract interaction of defi token",
    )
    address: str | None = Field(
        None,
        description="Ethereum address of the token",
    )
    type: Literal["defi", "base"] | None = Field(
        None,
        description="The type of the token (e.g., 'defi', 'base'). Note: Base Network also exists, it should not be confused with type.",
    )


class EnsoGetTokensOutput(BaseModel):
    res: list[TokenResponseCompact] | None
    error: str | None = None


class EnsoGetTokens(EnsoBaseTool):
    """
    Tool for interacting with the Enso API to retrieve cryptocurrency token information, including APY, symbol, address,
    protocol slug, token type, and underlying tokens.

    This class is designed to provide detailed insights into tokens managed by the Enso platform.
    It integrates with the Enso API and offers various options for filtering tokens based on optional inputs such as
    chain ID, protocol slug, token type, and underlying tokens. The main objective is to retrieve APY data
    and relevant information for the specified tokens, delivering structured output for further processing.

    Attributes:
        name (str): Name of the tool, specifically "enso_get_tokens".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_get_tokens"
    description: str = (
        "Enso Finance Token Information Tool: Retrieves detailed token information from the Enso Finance API, "
        "including APY, symbol, address, protocol slug, token type, and underlying tokens."
    )
    args_schema: Type[BaseModel] = EnsoGetTokensInput

    def _run(
        self,
        chainId: int = default_chain_id,
        protocolSlug: str = default_protocol_slug,
        **kwargs,
    ) -> EnsoGetTokensOutput:
        """Run the tool to get Tokens and APY.
        Args:
            chainId (int): The chain id of the network.
            protocolSlug (str): The protocol slug (e.g., 'aave-v2', 'aave-v3', 'compound-v2').
            **kwargs: kwargs for the tool with args schema defined in EnsoGetTokensInput.
        Returns:
            EnsoGetTokensOutput: A structured output containing the tokens APY data.

        Raises:
            Exception: If there's an error accessing the Enso API.
        """
        url = f"{base_url}/api/v1/tokens"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

        params = EnsoGetTokensInput(
            chainId=chainId, protocolSlug=protocolSlug, **kwargs
        ).model_dump(exclude_none=True)
        params["page"] = 1
        params["includeMetadata"] = "true"

        with httpx.Client() as client:
            try:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()
                json_dict = response.json()

                # filter the main tokens from config or the ones that have apy assigned.
                result = EnsoGetTokensOutput(res=list[TokenResponseCompact]())
                for item in json_dict["data"]:
                    if item.get("apy") or (item.get("symbol") in self.main_tokens):
                        result.res.append(TokenResponseCompact(**item))

                return result
            except httpx.RequestError as req_err:
                return EnsoGetTokensOutput(res=None, error=f"Request error: {req_err}")
            except httpx.HTTPStatusError as http_err:
                return EnsoGetTokensOutput(res=None, error=f"HTTP error: {http_err}")
            except Exception as e:
                return EnsoGetTokensOutput(res=None, error=str(e))

    async def _arun(self, **kwargs) -> EnsoGetTokensOutput:
        """Async implementation of the tool.

        This tool doesn't have a native async implementation, so we call the sync version.
        """
        return self._run()
