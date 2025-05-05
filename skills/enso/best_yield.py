from typing import List, Optional, Type

import httpx
from langchain.tools.base import ToolException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.base import SkillContext
from skills.enso.base import (
    EnsoBaseTool,
    base_url,
)
from utils.chain import NetworkId

# Chain ID for Base Mainnet
BASE_CHAIN_ID = int(NetworkId.BaseMainnet)


class EnsoGetBestYieldInput(BaseModel):
    """Input for finding the best yield for a token on a specific chain."""

    token_symbol: str = Field(
        "USDC",
        description="Symbol of the token to find the best yield for (e.g., 'USDC', 'ETH', 'USDT')",
    )
    chain_id: int = Field(
        BASE_CHAIN_ID,
        description="The blockchain chain ID. Default is Base Mainnet (8453)",
    )
    top_n: int = Field(
        5,
        description="Number of top yield options to return",
    )


class YieldOption(BaseModel):
    """Represents a yield option for a token."""

    protocol_name: str = Field(
        None, description="Name of the protocol offering the yield"
    )
    protocol_slug: str = Field(None, description="Slug of the protocol")
    token_name: str = Field(None, description="Name of the yield-bearing token")
    token_symbol: str = Field(None, description="Symbol of the yield-bearing token")
    token_address: str = Field(
        None, description="Contract address of the yield-bearing token"
    )
    primary_address: str = Field(
        None, description="Primary contract address for interacting with the protocol"
    )
    apy: float = Field(None, description="Annual Percentage Yield")
    tvl: Optional[float] = Field(None, description="Total Value Locked in the protocol")
    underlying_tokens: List[str] = Field(
        [], description="List of underlying token symbols"
    )


class EnsoGetBestYieldOutput(BaseModel):
    """Output containing the best yield options."""

    best_options: List[YieldOption] = Field(
        [], description="List of best yield options sorted by APY (descending)"
    )
    token_symbol: str = Field(None, description="Symbol of the token searched for")
    chain_id: int = Field(None, description="Chain ID searched")
    chain_name: str = Field(None, description="Name of the chain searched")


class EnsoGetBestYield(EnsoBaseTool):
    """
    Tool for finding the best yield options for a specific token across all protocols on a blockchain network.
    This tool analyzes yield data from various DeFi protocols and returns the top options sorted by APY.
    """

    name: str = "enso_get_best_yield"
    description: str = (
        "Find the best yield options for a specific token (default: USDC) across all protocols "
        "on a blockchain network (default: Base). Results are sorted by APY in descending order."
    )
    args_schema: Type[BaseModel] = EnsoGetBestYieldInput

    async def _arun(
        self,
        config: RunnableConfig,
        token_symbol: str = "USDC",
        chain_id: int = BASE_CHAIN_ID,
        top_n: int = 5,
        **kwargs,
    ) -> EnsoGetBestYieldOutput:
        """
        Run the tool to find the best yield options.

        Args:
            token_symbol (str): Symbol of the token to find the best yield for (default: USDC)
            chain_id (int): The chain id of the network (default: Base Mainnet)
            top_n (int): Number of top yield options to return

        Returns:
            EnsoGetBestYieldOutput: A structured output containing the top yield options.

        Raises:
            ToolException: If there's an error accessing the Enso API.
        """
        context: SkillContext = self.context_from_config(config)
        api_token = self.get_api_token(context)

        if not api_token:
            raise ToolException("No API token found for Enso Finance")

        # Get the chain name for the given chain ID
        chain_name = await self._get_chain_name(api_token, chain_id)

        # Get all protocols on the specified chain
        protocols = await self._get_protocols(api_token, chain_id)

        # Collect all yield options from all protocols
        all_yield_options = []

        for protocol in protocols:
            protocol_slug = protocol.get("slug")
            protocol_name = protocol.get("name")

            # Get yield-bearing tokens for this protocol
            tokens = await self._get_protocol_tokens(
                api_token, chain_id, protocol_slug, token_symbol
            )

            # Process tokens to extract yield options
            for token in tokens:
                # Skip tokens without APY information
                if token.get("apy") is None:
                    continue

                # Check if the token has USDC as an underlying token
                has_target_token = False
                underlying_token_symbols = []

                if token.get("underlyingTokens"):
                    for underlying in token.get("underlyingTokens", []):
                        underlying_symbol = underlying.get("symbol")
                        underlying_token_symbols.append(underlying_symbol)
                        if (
                            underlying_symbol
                            and underlying_symbol.upper() == token_symbol.upper()
                        ):
                            has_target_token = True

                # Skip if the token doesn't have the target token as underlying
                if not has_target_token and token.get("symbol") != token_symbol.upper():
                    continue

                # Create a yield option
                yield_option = YieldOption(
                    protocol_name=protocol_name,
                    protocol_slug=protocol_slug,
                    token_name=token.get("name"),
                    token_symbol=token.get("symbol"),
                    token_address=token.get("address"),
                    primary_address=token.get("primaryAddress"),
                    apy=token.get("apy"),
                    tvl=token.get("tvl"),
                    underlying_tokens=underlying_token_symbols,
                )

                all_yield_options.append(yield_option)

        # Sort yield options by APY (descending)
        sorted_options = sorted(all_yield_options, key=lambda x: x.apy, reverse=True)

        # Take the top N options
        top_options = sorted_options[:top_n]

        return EnsoGetBestYieldOutput(
            best_options=top_options,
            token_symbol=token_symbol,
            chain_id=chain_id,
            chain_name=chain_name,
        )

    async def _get_chain_name(self, api_token: str, chain_id: int) -> str:
        """
        Get the name of a chain by its ID.

        Args:
            api_token (str): The Enso API token
            chain_id (int): The chain ID to look up

        Returns:
            str: The name of the chain, or "Unknown" if not found
        """
        url = f"{base_url}/api/v1/networks"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                networks = response.json()

                for network in networks:
                    if network.get("id") == chain_id:
                        return network.get("name", "Unknown")

                return "Unknown"
            except Exception:
                return "Unknown"

    async def _get_protocols(self, api_token: str, chain_id: int) -> list:
        """
        Get all protocols available on a specific chain.

        Args:
            api_token (str): The Enso API token
            chain_id (int): Chain ID to filter protocols by

        Returns:
            list: List of protocol data
        """
        url = f"{base_url}/api/v1/protocols"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        params = {"chainId": chain_id}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"Request error from Enso API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"HTTP error from Enso API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"Error from Enso API: {e}") from e

    async def _get_protocol_tokens(
        self, api_token: str, chain_id: int, protocol_slug: str, token_symbol: str
    ) -> list:
        """
        Get tokens for a specific protocol that involve the target token.

        Args:
            api_token (str): The Enso API token
            chain_id (int): Chain ID for the tokens
            protocol_slug (str): Protocol slug to filter tokens by
            token_symbol (str): Symbol of the token to search for

        Returns:
            list: List of token data
        """
        url = f"{base_url}/api/v1/tokens"

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        params = {
            "chainId": chain_id,
            "protocolSlug": protocol_slug,
            "includeMetadata": True,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json().get("data", [])
            except httpx.RequestError:
                return []
            except httpx.HTTPStatusError:
                return []
            except Exception:
                return []
