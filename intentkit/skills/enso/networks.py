import logging
from typing import Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from .base import EnsoBaseTool, base_url

logger = logging.getLogger(__name__)


class EnsoGetNetworksInput(BaseModel):
    """
    Input model for retrieving networks.
    """


class ConnectedNetwork(BaseModel):
    """
    Represents a single network connection.
    """

    id: int | None = Field(None, description="Unique identifier of the network")
    name: str | None = Field(None, description="Name of the network")
    isConnected: bool | None = Field(
        None, description="Indicates if the network is connected"
    )


class EnsoGetNetworksOutput(BaseModel):
    """
    Output model for retrieving networks.
    """

    res: list[ConnectedNetwork] | None = Field(
        None, description="Response containing networks and metadata"
    )


class EnsoGetNetworks(EnsoBaseTool):
    """
    Tool for retrieving networks and their corresponding chainId, the output should be kept.
    """

    name: str = "enso_get_networks"
    description: str = "Retrieve networks supported by the Enso API"
    args_schema: Type[BaseModel] = EnsoGetNetworksInput

    async def _arun(self, **kwargs) -> EnsoGetNetworksOutput:
        """
        Function to request the list of supported networks and their chain id and name.

        Returns:
            EnsoGetNetworksOutput: A structured output containing the network list or an error message.
        """
        url = f"{base_url}/api/v1/networks"

        context = self.get_context()
        api_token = self.get_api_token(context)
        logger.debug(f"api_token: {api_token}")
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        async with httpx.AsyncClient() as client:
            try:
                # Send the GET request
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                # Parse the response JSON into the NetworkResponse model
                json_dict = response.json()

                networks = []
                networks_memory = {}
                for item in json_dict:
                    network = ConnectedNetwork(**item)
                    networks.append(network)
                    networks_memory[str(network.id)] = network.model_dump(
                        exclude_none=True
                    )

                await self.skill_store.save_agent_skill_data(
                    context.agent_id,
                    "enso_get_networks",
                    "networks",
                    networks_memory,
                )

                return EnsoGetNetworksOutput(res=networks)
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Enso API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Enso API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"error from Enso API: {e}") from e
