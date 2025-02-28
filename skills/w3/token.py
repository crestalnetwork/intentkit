from typing import Type

from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from utils.chain import NetworkTitle, get_network_by_title

from .base import Web3BaseTool


class W3TokenInfo(BaseModel):
    """
    Represents information about a Web3 token.

    This class encapsulates various attributes of a token, including its symbol,
    chain ID, name, decimals, and addresses. It's designed to provide a structured
    way to store and access token metadata.
    """

    symbol: str | None = Field(
        None, description="The token's symbol (e.g., ETH, USDC)."
    )
    chain_id: str | None = Field(
        None,
        description="The ID of the blockchain network the token belongs to (e.g., '1' for Ethereum Mainnet). this is the Network enum id field.",
    )
    is_well_known: bool | None = Field(
        False,
        description="Indicates whether the token is widely recognized or a standard token.",
    )
    name: str | None = Field(
        None, description="The full name of the token (e.g., Ethereum, USD Coin)."
    )
    decimals: int | None = Field(
        None,
        description="The number of decimal places the token uses (e.g., 18 for ETH, 6 for USDC).",
    )
    address: str | None = Field(
        None, description="The token's contract address on the blockchain."
    )
    primary_address: str | None = Field(
        None,
        description="""
        The primary address of the token. In some cases, tokens have multiple addresses,
        but this field indicates the main or canonical address.
        """,
    )
    token_type: str | None = Field(
        None, description="The type of token (e.g., defi, base)."
    )
    protocol_slug: str | None = Field(
        None,
        description="A slug representing the protocol or platform associated with the token.",
    )


class GetTokenInput(BaseModel):
    """
    Input model for fetching information about an specific token of a particular network.
    """

    symbol: str = Field(..., description="The token symbol.")
    network_title: NetworkTitle = Field(
        ...,
        description="The network of the token. it should be filled according to get_networks tool and user request",
    )


class GetTokenOutput(BaseModel):
    """
    Output model for token.
    """

    token: W3TokenInfo = Field(
        ..., description="The information of the requested token."
    )


class GetToken(Web3BaseTool):
    """
    This tool returns the Web3 token information.

    Attributes:
        name (str): Name of the tool, specifically "w3_get_token".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "w3_get_token"
    description: str = "This tool returns the token information."
    args_schema: Type[BaseModel] = GetTokenInput

    def _run(self, symbol: str, network_title: NetworkTitle) -> GetTokenOutput:
        """
        Run the tool to fetch the Web3 token information.

        Returns:
            GetTokenOutput: A structured output containing the token information.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, symbol: str, network_title: NetworkTitle) -> GetTokenOutput:
        """
        Run the tool to fetch the Web3 token information.

        Arg:
            symbol(str): the symbol of the token.
            network_title(NetworkTitle): the network of the token.

        Returns:
            GetTokenOutput: A structured output containing the token information.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """

        w3token = await self.system_store.get_token(
            symbol=symbol, network=get_network_by_title(network_title)
        )

        if not w3token:
            raise ToolException("could not find the token")

        return GetTokenOutput(
            token=W3TokenInfo(**w3token.model_dump(exclude_none=True))
        )


class GetWellknownTokensInput(BaseModel):
    """
    Input model for fetching well-known tokens and their corresponding information like network, network id (chain id).
    """

    pass


class GetWellknownTokensOutput(BaseModel):
    """
    Output model for Wellknown tokens.
    """

    tokens: list[W3TokenInfo] = Field(..., description="The list of well-known tokens.")


class GetWellknownTokens(Web3BaseTool):
    """
    This tool returns well-known tokens and their corresponding information.

    Attributes:
        name (str): Name of the tool, specifically "w3_get_wellknown_tokens".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "w3_get_wellknown_tokens"
    description: str = (
        "This tool returns well-known tokens and their corresponding information."
    )
    args_schema: Type[BaseModel] = GetWellknownTokensInput

    def _run(self) -> GetWellknownTokensOutput:
        """
        Run the tool to fetch well-known tokens and their corresponding information.

        Returns:
            GetWellknownTokensOutput: A structured output containing the list of well-known tokens.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> GetWellknownTokensOutput:
        """
        Run the tool to fetch well-known tokens and their corresponding information.

        Returns:
            GetWellknownTokensOutput: A structured output containing the token information.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """

        tokens = await self.system_store.get_all_wellknown_tokens()

        if not tokens:
            raise ToolException("could not find the token")

        return GetWellknownTokensOutput(
            tokens=[
                W3TokenInfo(**w3token.model_dump(exclude_none=True))
                for w3token in tokens
            ]
        )
