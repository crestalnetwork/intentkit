from typing import Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.enso.networks import EnsoGetNetworks

from .base import EnsoBaseTool, base_url, default_chain_id


class EnsoRouteShortcutInput(BaseModel):
    """
    Input model for finding best route for swap or deposit.
    """

    broadcast_requested: bool = Field(
        False,
        description="Whether to broadcast the transaction or not, this is false by default.",
    )
    chainId: int = Field(
        default_chain_id,
        description="(Optional) Chain ID of the network to execute the transaction on. the default value is the chain_id extracted from networks according to tokenIn and tokenOut",
    )
    amountIn: list[int] = Field(
        description="Amount of tokenIn to swap in wei, you should multiply user's requested value by token decimals."
    )
    tokenIn: list[str] = Field(
        description="Ethereum address of the token to swap or enter into a position from (For ETH, use 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee)."
    )
    tokenOut: list[str] = Field(
        description="Ethereum address of the token to swap or enter into a position to (For ETH, use 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee)."
    )
    # Optional inputs
    # routingStrategy: Literal["router", "delegate", "ensowallet", None] = Field(
    #     None,
    #     description="(Optional) Routing strategy to use. Options: 'ensowallet', 'router', 'delegate'.",
    # )
    # receiver: str | None = Field(
    #     None, description="(Optional) Ethereum address of the receiver of the tokenOut."
    # )
    # spender: str | None = Field(
    #     None, description="(Optional) Ethereum address of the spender of the tokenIn."
    # )
    # amountOut: list[str] | None = Field(
    #     None, description="(Optional) Amount of tokenOut to receive."
    # )
    # minAmountOut: list[str] | None = Field(
    #     None,
    #     description="(Optional) Minimum amount out in wei. If specified, slippage should not be specified.",
    # )
    # slippage: str | None = Field(
    #     None,
    #     description="(Optional) Slippage in basis points (1/10000). If specified, minAmountOut should not be specified.",
    # )
    # fee: list[str] | None = Field(
    #     None,
    #     description="(Optional) Fee in basis points (1/10000) for each amountIn value.",
    # )
    # feeReceiver: str | None = Field(
    #     None,
    #     description="(Optional) Ethereum address that will receive the collected fee if fee was provided.",
    # )
    # disableRFQs: bool | None = Field(
    #     None, description="(Optional) Exclude RFQ sources from routes."
    # )
    # ignoreAggregators: list[str] | None = Field(
    #     None, description="(Optional) List of swap aggregators to ignore."
    # )
    # ignoreStandards: list[str] | None = Field(
    #     None, description="(Optional) List of standards to ignore."
    # )
    # variableEstimates: dict | None = Field(
    #     None, description="Variable estimates for the route."
    # )


class Route(BaseModel):
    tokenIn: list[str] | None = Field(
        None,
        description="Ethereum address of the token to swap or enter into a position from.",
    )
    tokenOut: list[str] | None = Field(
        None,
        description="Ethereum address of the token to swap or enter into a position to.",
    )
    protocol: str | None = Field(None, description="Protocol used for finding route.")
    action: str | None = Field(
        None, description="Action has been done for route (e.g. swap)."
    )
    # internalRoutes: list[str] | None = Field(
    #     None, description="Internal routes needed for the route."
    # )


class EnsoRouteShortcutOutput(BaseModel):
    """
    Output model for broadcasting a transaction.
    """

    network: str = Field(
        "The network name of the transaction.",
    )
    amountOut: str | dict | None = Field(
        None,
        description="The final calculated amountOut as an object. you should multiply its value by tokenOut decimals.",
    )
    priceImpact: float | None = Field(
        None,
        description="Price impact in basis points, it is null if USD price is not found.",
    )
    txHash: str | None = Field(
        None, description="The transaction hash of the broadcasted transaction."
    )
    # gas: str | None = Field(
    #     None,
    #     description="Estimated gas amount for the transaction.",
    # )
    # feeAmount: list[str] | None = Field(
    #     None,
    #     description="An array of the fee amounts collected for each tokenIn.",
    # )
    # createdAt: int | None = Field(
    #     None, description="Block number the transaction was created on."
    # )
    # route: list[Route] | None = Field(
    #     None, description="Route that the shortcut will use."
    # )

    # def __str__(self):
    #     """
    #     Returns the summary attribute as a string.
    #     """
    #     return f"network:{self.network}, amount out: {self.amountOut}, price impact: {self.priceImpact}, tx hash: {self.txHash}"


class EnsoRouteShortcut(EnsoBaseTool):
    """
    This tool finds the optimal execution route path for swap or deposit across a multitude of DeFi protocols such as liquidity pools,
    lending platforms, automated market makers, yield optimizers, and more. This allows for maximized capital efficiency
    and yield optimization, taking into account return rates, gas costs, and slippage.

    Important: the amountOut should be divided by tokenOut decimals before returning the result.

    This tool is able to broadcast the transaction to the network if the user explicitly requests it. otherwise,
    broadcast_requested is always false.

    Deposit means to supply the underlying token to its parent token. (e.g. deposit USDC to receive aBasUSDC).

    Attributes:
        name (str): Name of the tool, specifically "enso_route_shortcut".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_route_shortcut"
    description: str = "This tool is used specifically for broadcasting a route transaction calldata to the network. It should only be used when the user explicitly requests to broadcast a route transaction with routeId."
    args_schema: Type[BaseModel] = EnsoRouteShortcutInput

    async def _arun(
        self,
        amountIn: list[int],
        tokenIn: list[str],
        tokenOut: list[str],
        chainId: int = default_chain_id,
        broadcast_requested: bool = False,
        **kwargs,
    ) -> EnsoRouteShortcutOutput:
        """
        Run the tool to get swap route information.

        Args:
            amountIn (list[int]): Amount of tokenIn to swap in wei, you should multiply user's requested value by token decimals.
            tokenIn (list[str]): Ethereum address of the token to swap or enter into a position from (For ETH, use 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee).
            tokenOut (list[str]): Ethereum address of the token to swap or enter into a position to (For ETH, use 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee).
            chainId (int): The chain id of the network to be used for swap, deposit and routing.
            broadcast_requested (bool): User should ask for broadcasting the transaction explicitly, otherwise it is always false.

        Returns:
            EnsoRouteShortcutOutput: The response containing route shortcut information.
        """

        context = self.get_context()
        agent_id = context.agent_id
        api_token = self.get_api_token(context)
        account = await self.get_account(context)

        async with httpx.AsyncClient() as client:
            try:
                network_name = None
                networks = await self.skill_store.get_agent_skill_data(
                    agent_id, "enso_get_networks", "networks"
                )

                if networks:
                    network_name = (
                        networks.get(str(chainId)).get("name")
                        if networks.get(str(chainId))
                        else None
                    )
                if network_name is None:
                    networks = await EnsoGetNetworks(
                        skill_store=self.skill_store,
                    ).arun()

                    for network in networks.res:
                        if network.id == chainId:
                            network_name = network.name

                if not network_name:
                    raise ToolException(
                        f"network name not found for chainId: {chainId}"
                    )

                headers = {
                    "accept": "application/json",
                    "Authorization": f"Bearer {api_token}",
                }

                token_decimals = await self.skill_store.get_agent_skill_data(
                    agent_id,
                    "enso_get_tokens",
                    "decimals",
                )

                if not token_decimals:
                    raise ToolException(
                        "there is not enough information, enso_get_tokens should be called for data, at first."
                    )

                if not token_decimals.get(tokenOut[0]):
                    raise ToolException(
                        f"token decimals information for token {tokenOut[0]} not found"
                    )

                if not token_decimals.get(tokenIn[0]):
                    raise ToolException(
                        f"token decimals information for token {tokenIn[0]} not found"
                    )

                url = f"{base_url}/api/v1/shortcuts/route"

                # Prepare query parameters
                params = EnsoRouteShortcutInput(
                    chainId=chainId,
                    amountIn=amountIn,
                    tokenIn=tokenIn,
                    tokenOut=tokenOut,
                ).model_dump(exclude_none=True)

                params["fromAddress"] = account.address

                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()  # Raise HTTPError for non-2xx responses
                json_dict = response.json()

                res = EnsoRouteShortcutOutput(**json_dict)
                res.network = network_name

                res.amountOut = str(
                    float(res.amountOut) / 10 ** token_decimals[tokenOut[0]]
                )

                if broadcast_requested:
                    # Use the wallet provider to send the transaction
                    wallet_provider = await self.get_wallet_provider(context)

                    # Extract transaction data from the Enso API response
                    tx_data = json_dict.get("tx", {})
                    if tx_data:
                        # Send the transaction using the wallet provider
                        tx_hash = wallet_provider.send_transaction(
                            {
                                "to": tx_data.get("to"),
                                "data": tx_data.get("data", "0x"),
                                "value": tx_data.get("value", 0),
                            }
                        )

                        # Wait for transaction confirmation
                        wallet_provider.wait_for_transaction_receipt(tx_hash)
                        res.txHash = tx_hash
                    else:
                        # For now, return a placeholder transaction hash if no tx data
                        res.txHash = "0x0000000000000000000000000000000000000000000000000000000000000000"

                return res

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
