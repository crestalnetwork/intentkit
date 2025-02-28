from typing import Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from utils.chain import (
    ChainType,
    EventSignature,
    NetworkTitle,
    get_network_by_title,
    get_padded_address,
)

from .base import Web3BaseTool


class GetTransfersInput(BaseModel):
    """
    Input model for fetching Token transfers to a specific address.
    """

    network_title: NetworkTitle = Field(
        ...,
        description="Network to fetch Token transfers from. this should be filled from the output of get_networks tool",
    )
    receiver_address: str = Field(
        ...,
        description="Ethereum address to fetch Token transfers for. it can be agent's wallet address or user's wallet(if requested)",
    )
    token_address: str = Field(
        ...,
        description="Ethereum address to fetch Token transfers for. this should be filled from the output of get_networks tool according to chain_id",
    )
    token_decimals: int = Field(
        ...,
        description="The token decimals. this should be filled from the output of get_networks tool according to chain_id and token",
    )
    first_block: int = Field(
        ...,
        description="The first block filled with the output of w3_get_block_range_by_time tool according to user's requested time range.",
    )
    last_block: int = Field(
        ...,
        description="The last block filled with the output of w3_get_block_range_by_time tool according to user's requested time range.",
    )


class EvmLogEntry(BaseModel):
    address: str | None = Field(
        None, description="The contract address that generated the log."
    )
    topics: list[str] | None = Field(
        None, description="An array of topics associated with the log."
    )
    data: str | None = Field(None, description="The data field of the log.")
    blockNumber: str | None = Field(
        None, description="The block number where the log was generated."
    )
    transactionHash: str | None = Field(
        None, description="The transaction hash that generated the log."
    )
    transactionIndex: str | None = Field(
        None, description="The transaction index within the block."
    )
    blockHash: str | None = Field(
        None, description="The block hash where the log was generated."
    )
    logIndex: str | None = Field(None, description="The log index within the block.")
    removed: bool | None = Field(
        None, description="Indicates if the log was removed due to a reorg."
    )


class Transfer(BaseModel):
    amount: float | None = Field(None, description="The transferred amount.")
    transactionHash: str | None = Field(
        None, description="The transaction hash that generated the log."
    )


class GetTransfersOutput(BaseModel):
    """
    Output model for Token transfers.
    """

    transfers: list[Transfer]


class GetTransfers(Web3BaseTool):
    """
    This tool fetches all token transfers to a specific address using the Quicknode API.

    Attributes:
        name (str): Name of the tool, specifically "tx_get_token_transfers".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "tx_get_token_transfers"
    description: str = (
        "This tool fetches all token transfers to a specific address using the Quicknode API."
    )
    args_schema: Type[BaseModel] = GetTransfersInput

    def _run(
        self,
        receiver_address: str,
        network_title: NetworkTitle,
        token_address: str,
        token_decimals: int,
        first_block: int,
        last_block: int,
    ) -> GetTransfersOutput:
        """Run the tool to fetch all token transfers to a specific address using the Quicknode API.

        Returns:
            GetTransfersOutput: A structured output containing the result of tokens and APYs.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(
        self,
        receiver_address: str,
        network_title: NetworkTitle,
        token_address: str,
        token_decimals: int,
        first_block: int,
        last_block: int,
    ) -> GetTransfersOutput:
        """Run the tool to fetch all token transfers to a specific address using the Quicknode API.
        Args:
            receiver_address (str): The receiver account address.
            network_title (NetworkTitle): The requested network title.
            token_address (str): The address of the token smart contract.
            token_decimals (int): The token decimals
            first_block (int): the first block for querying transactions, this should be filled with the output of w3_get_block_range_by_time according to the requested start timestamp by user.
            last_block (int): the last block for querying transactions, this should be filled with the output of w3_get_block_range_by_time according to the requested end timestamp by user.
        Returns:
            GetTransfersOutput: A structured output containing the tokens APY data.

        Raises:
            Exception: If there's an error accessing the Quicknode API.
        """

        network = get_network_by_title(network_title)
        chain_type = network.value.chain.value.chain_type
        if chain_type != ChainType.EVM:
            raise ToolException(f"chain type is not supported {chain_type}")

        chain_config = self.chain_provider.get_chain_config(network_title)
        headers = {
            "accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            try:
                json = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_blockNumber",
                    "params": [],
                }
                response = await client.post(
                    chain_config.rpc_url, headers=headers, json=json
                )
                response.raise_for_status()
                json_dict = response.json()

                json = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getLogs",
                    "params": [
                        {
                            "address": token_address,
                            "topics": [
                                EventSignature.Transfer.value,
                                None,
                                get_padded_address(receiver_address),
                            ],
                            "fromBlock": hex(first_block),
                            "toBlock": hex(last_block),
                        }
                    ],
                }
                response = await client.post(
                    chain_config.rpc_url, headers=headers, json=json
                )
                response.raise_for_status()
                json_dict = response.json()

                res = GetTransfersOutput(transfers=[])
                for item in json_dict["result"]:
                    log_item = EvmLogEntry(**item)
                    amount_wei = int(log_item.data, 16)
                    amount = amount_wei / (10**token_decimals)
                    res.transfers.append(
                        Transfer(
                            amount=amount, transactionHash=log_item.transactionHash
                        )
                    )
                return res
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Quicknode API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Quicknode API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"error from Quicknode API: {e}") from e
