from typing import Tuple, Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from utils.random import generate_tx_confirm_string
from utils.tx import EvmTx

from .base import EnsoBaseTool, base_url, default_chain_id


class EnsoGetRouteShortcutInput(BaseModel):
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


class Transaction(BaseModel):
    data: str = Field(None, description="Data of the transaction.")
    to: str = Field(
        None, description="Ethereum address of the receiver of the transaction."
    )
    from_: str = Field(
        None, description="Ethereum address of the sender of the transaction."
    )
    value: str = Field(None, description="Amount of token to send.")


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


class EnsoGetRouteShortcutOutput(BaseModel):
    """
    Output schema for the `/api/v1/shortcuts/route` GET endpoint.
    """

    txRef: str = Field(
        description="The reference code is the unique identifier for the transaction call data.",
    )
    gas: str | None = Field(
        None,
        description="Gas amount for the transaction.",
    )
    amountOut: str | dict | None = Field(
        None,
        description="The final calculated amountOut as an object. you should multiply the string float value by tokenOut decimals.",
    )
    priceImpact: float | None = Field(
        None,
        description="Price impact in basis points, it is null if USD price is not found.",
    )
    feeAmount: list[str] | None = Field(
        None,
        description="An array of the fee amounts collected for each tokenIn.",
    )
    # createdAt: int | None = Field(
    #     None, description="Block number the transaction was created on."
    # )
    # route: list[Route] | None = Field(
    #     None, description="Route that the shortcut will use."
    # )

    def __str__(self):
        """
        Returns the summary attribute as a string.
        """
        return f"tx reference: {self.txRef}, amount out: {self.amountOut}, price impact: {self.priceImpact}, gas: {self.gas}, fee amount: {self.feeAmount}"


class EnsoGetRouteShortcutArtifact(BaseModel):
    """
    Artifact model for the EnsoGetRouteShortcut tool.
    """

    txRef: str = Field(
        description="This will be used by the other tools to broadcast the transaction."
    )


class EnsoGetRouteShortcut(EnsoBaseTool):
    """
    This tool deposits or swaps the optimal execution route path across a multitude of DeFi protocols such as liquidity pools,
    lending platforms, automated market makers, yield optimizers, and more. This allows for maximized capital efficiency
    and yield optimization, taking into account return rates, gas costs, and slippage.

    IMPORTANT: For each request, the required input parameters should be extracted from user's message, do not fill it
    from your memory, and you should include the network name in the response. the confirmation_code should be shown
    to the users if the API call gets successful response.

    Deposit means to supply the underlying token to its parent token. (e.g. deposit USDC to receive aBasUSDC).

    Attributes:
        name (str): Name of the tool, specifically "enso_get_route_shortcut".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_get_route_shortcut"
    description: str = "This tool optimizes and performs DeFi swap, deposit, identifying the most efficient execution path across various protocols (e.g., liquidity pools, lending platforms) by considering factors like return rates, gas costs, and slippage."
    args_schema: Type[BaseModel] = EnsoGetRouteShortcutInput
    response_format: str = "content_and_artifact"

    def _run(
        self,
        amountIn: list[int],
        tokenIn: list[str],
        tokenOut: list[str],
        chainId: int = default_chain_id,
    ) -> Tuple[EnsoGetRouteShortcutOutput, EnsoGetRouteShortcutArtifact]:
        """
        Run the tool to get swap route information.

        Args:
            amountIn (list[int]): Amount of tokenIn to swap in wei, you should multiply user's requested value by token decimals.
            tokenIn (list[str]): Ethereum address of the token to swap or enter into a position from (For ETH, use 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee).
            tokenOut (list[str]): Ethereum address of the token to swap or enter into a position to (For ETH, use 0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee).
            chainId (int): The chain id of the network to be used for swap, deposit and routing.

        Returns:
            EnsoGetRouteShortcutOutput: The response containing route shortcut information.
        """
        url = f"{base_url}/api/v1/shortcuts/route"

        headers = {
            "Authorization": f"Bearer {self.api_token}",
        }

        # Prepare query parameters
        params = EnsoGetRouteShortcutInput(
            chainId=chainId,
            amountIn=amountIn,
            tokenIn=tokenIn,
            tokenOut=tokenOut,
        ).model_dump(exclude_none=True)

        params["fromAddress"] = self.from_address

        with httpx.Client() as client:
            try:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()  # Raise HTTPError for non-2xx responses
                json_dict = response.json()
                # Parse and return the response as a RouteShortcutGetTransaction object
                tx_ref = generate_tx_confirm_string(10)
                json_dict["txRef"] = tx_ref

                content = EnsoGetRouteShortcutOutput(**json_dict)

                tx_dict = json_dict.get("tx")
                evm_tx = EvmTx(**tx_dict)
                evm_tx.gas = content.gas

                self.store.save_agent_skill_data(
                    self.agent_id,
                    self.name,
                    tx_ref,
                    evm_tx.model_dump(exclude_none=True),
                )

                return (
                    content,
                    EnsoGetRouteShortcutArtifact(
                        txRef=tx_ref,
                    ),
                )

            # except httpx.RequestError as req_err:
            #     raise ToolException("request error from Enso API") from req_err
            # except httpx.HTTPStatusError as http_err:
            #     raise ToolException("http error from Enso API") from http_err
            except Exception as e:
                raise ToolException(f"error from Enso API: {e}") from e
