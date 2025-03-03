from typing import Type

from pydantic import BaseModel, Field

from utils.chain import Chain, Network

from .base import Web3BaseTool


class GetNetworksInput(BaseModel):
    """
    Input model for fetching information about an specific network by name.
    """

    pass


class GetNetworksOutput(BaseModel):
    """
    Output model for Networks.
    """

    chains: list[Chain] = Field(
        ..., description="List of all supported blockchain chains."
    )
    networks: list[Network] = Field(
        ..., description="List of all supported networks information."
    )


class GetNetworks(Web3BaseTool):
    """
    This tool returns all supported blockchains, their networks and corresponding id list.

    Attributes:
        name (str): Name of the tool, specifically "w3_get_networks".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "w3_get_networks"
    description: str = (
        "This tool returns all supported blockchains, their networks and corresponding id list."
    )
    args_schema: Type[BaseModel] = GetNetworksInput

    def _run(self) -> GetNetworksOutput:
        """
        Run the tool to fetch all supported blockchains, their networks and corresponding id list.

        Returns:
            GetTransfersOutput: A structured output containing blockchains, their networks and id list.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> GetNetworksOutput:
        """
        Run the tool to fetch all supported blockchains, their networks and corresponding id list.

        Returns:
            GetTransfersOutput: A structured output containing blockchains, their networks and id list.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """

        return GetNetworksOutput(
            chains=[chain for chain in Chain],
            networks=[network for network in Network],
        )
