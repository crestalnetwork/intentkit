from typing import Literal, Tuple, Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from .base import EnsoBaseTool, base_url, default_chain_id


class EnsoGetBalancesInput(BaseModel):
    """
    Input model for retrieving wallet balances.
    """

    chainId: int = Field(
        default_chain_id, description="Chain ID of the blockchain network"
    )
    # eoaAddress: str = Field(
    #     description="Address of the eoa with which to associate the ensoWallet for balances"
    # )
    # useEoa: bool = Field(
    #     description="If true returns balances for the provided eoaAddress, instead of the associated ensoWallet"
    # )


class WalletBalance(BaseModel):
    token: str | None = Field(None, description="The address of the token")
    amount: str | None = Field(None, description="The unformatted balance of the token")
    decimals: int | None = Field(None, ge=0, description="The number of decimals")
    price: float | None = Field(None, description="Price of the token in usd")


class EnsoGetBalancesOutput(BaseModel):
    """
    Output model for retrieving wallet balances.
    """

    res: list[WalletBalance] | None = Field(
        None, description="The wallet's balances along with token details."
    )


class EnsoGetWalletBalances(EnsoBaseTool):
    """
    This tool allows querying for first 20 token balances of a specific wallet
    and blockchain network.

    Attributes:
        name (str): Name of the tool, specifically "enso_get_wallet_balances".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_get_wallet_balances"
    description: str = (
        "Retrieve token balances of a wallet on a specified blockchain network."
    )
    args_schema: Type[BaseModel] = EnsoGetBalancesInput

    async def _arun(
        self,
        chainId: int = default_chain_id,
        **kwargs,
    ) -> EnsoGetBalancesOutput:
        """
        Run the tool to get token balances of a wallet.

        Args:
            chainId (int): Chain ID of the blockchain network.

        Returns:
            EnsoGetBalancesOutput: The list of balances or an error message.
        """
        url = f"{base_url}/api/v1/wallet/balances"

        context = self.get_context()
        api_token = self.get_api_token(context)
        account = await self.get_account(context)
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        params = EnsoGetBalancesInput(chainId=chainId).model_dump(exclude_none=True)
        params["eoaAddress"] = account.address
        params["useEoa"] = True

        async with httpx.AsyncClient() as client:
            try:
                # Send the GET request
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()

                # Map the response JSON into the WalletBalance model
                json_dict = response.json()[:20]
                res = [WalletBalance(**item) for item in json_dict]

                # Return the parsed response
                return EnsoGetBalancesOutput(res=res)
            except httpx.RequestError as req_err:
                raise ToolException("request error from Enso API") from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException("http error from Enso API") from http_err
            except Exception as e:
                raise ToolException(f"error from Enso API: {e}") from e


class EnsoGetApprovalsInput(BaseModel):
    """
    Input model for retrieving wallet approvals.
    """

    chainId: int = Field(
        default_chain_id, description="Chain ID of the blockchain network"
    )
    fromAddress: str = Field(description="Address of the wallet")
    routingStrategy: Literal["ensowallet", "router", "delegate"] | None = Field(
        None, description="Routing strategy to use"
    )


class WalletAllowance(BaseModel):
    token: str | None = Field(None, description="The token address")
    allowance: str | None = Field(None, description="The amount of tokens approved")
    spender: str | None = Field(None, description="The spender address")


class EnsoGetApprovalsOutput(BaseModel):
    """
    Output model for retrieving wallet approvals.
    """

    res: list[WalletAllowance] | None = Field(
        None, description="Response containing the list of token approvals."
    )


class EnsoGetWalletApprovals(EnsoBaseTool):
    """
    This tool allows querying for first 50 token spend approvals associated with a specific wallet
    and blockchain network.

    Attributes:
        name (str): Name of the tool, specifically "enso_get_wallet_approvals".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_get_wallet_approvals"
    description: str = (
        "Retrieve token spend approvals for a wallet on a specified blockchain network."
    )
    args_schema: Type[BaseModel] = EnsoGetApprovalsOutput

    async def _arun(
        self,
        chainId: int = default_chain_id,
        **kwargs,
    ) -> EnsoGetApprovalsOutput:
        """
        Run the tool to get token approvals for a wallet.

        Args:
            chainId (int): Chain ID of the blockchain network.
            **kwargs: optional kwargs for the tool with args schema defined in EnsoGetApprovalsInput.

        Returns:
            EnsoGetApprovalsOutput: The list of approvals or an error message.
        """
        url = f"{base_url}/api/v1/wallet/approvals"

        context = self.get_context()
        api_token = self.get_api_token(context)
        account = await self.get_account(context)

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        params = EnsoGetApprovalsInput(
            chainId=chainId,
            fromAddress=account.address,
        )

        if kwargs.get("routingStrategy"):
            params.routingStrategy = kwargs["routingStrategy"]

        async with httpx.AsyncClient() as client:
            try:
                # Send the GET request
                response = await client.get(
                    url, headers=headers, params=params.model_dump(exclude_none=True)
                )
                response.raise_for_status()

                # Map the response JSON into the ApprovalsResponse model
                json_dict = response.json()[:50]
                res = [WalletAllowance(**item) for item in json_dict]

                # Return the parsed response
                return EnsoGetApprovalsOutput(res=res)
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


class EnsoWalletApproveInput(BaseModel):
    """
    Input model for approve the wallet.
    """

    tokenAddress: str = Field(description="ERC20 token address of the token to approve")
    amount: int = Field(description="Amount of tokens to approve in wei")
    chainId: int = Field(
        default_chain_id, description="Chain ID of the blockchain network"
    )
    routingStrategy: Literal["ensowallet", "router", "delegate"] | None = Field(
        None, description="Routing strategy to use"
    )


class EnsoWalletApproveOutput(BaseModel):
    """
    Output model for approve token for the wallet.
    """

    gas: str | None = Field(None, description="The gas estimate for the transaction")
    token: str | None = Field(None, description="The token address to approve")
    amount: str | None = Field(None, description="The amount of tokens to approve")
    spender: str | None = Field(None, description="The spender address to approve")


class EnsoWalletApproveArtifact(BaseModel):
    """
    Output model for approve token for the wallet.
    """

    tx: object | None = Field(None, description="The tx object to use in `ethers`")
    txHash: str | None = Field(None, description="The transaction hash")


class EnsoWalletApprove(EnsoBaseTool):
    """
    This tool is used specifically for broadcasting a ERC20 token spending approval transaction to the network.
    It should only be used when the user explicitly requests to broadcast an approval transaction with a specific amount for a certain token.

    **Example Usage:**

    "Broadcast an approval transaction for 10 USDC to the wallet."

    **Important:**
    - This tool should be used with extreme caution.
    - Approving token spending grants another account permission to spend your tokens.

    Attributes:
        name (str): Name of the tool, specifically "enso_wallet_approve".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "enso_wallet_approve"
    description: str = "This tool is used specifically for broadcasting a ERC20 token spending approval transaction to the network. It should only be used when the user explicitly requests to broadcast an approval transaction with a specific amount for a certain token."
    args_schema: Type[BaseModel] = EnsoWalletApproveInput
    response_format: str = "content_and_artifact"

    # def _run(
    #     self,
    #     tokenAddress: str,
    #     amount: int,
    #     chainId: int = default_chain_id,
    #     **kwargs,
    # ) -> Tuple[EnsoBroadcastWalletApproveOutput, EnsoBroadcastWalletApproveArtifact]:
    #     """Run the tool to approve enso router for a wallet.

    #     Returns:
    #         Tuple[EnsoBroadcastWalletApproveOutput, EnsoBroadcastWalletApproveArtifact]: A structured output containing the result of token approval.

    #     Raises:
    #         Exception: If there's an error accessing the Enso API.
    #     """
    #     raise NotImplementedError("Use _arun instead")

    async def _arun(
        self,
        tokenAddress: str,
        amount: int,
        chainId: int = default_chain_id,
        **kwargs,
    ) -> Tuple[EnsoWalletApproveOutput, EnsoWalletApproveArtifact]:
        """
        Run the tool to approve enso router for a wallet.

        Args:
            tokenAddress (str): ERC20 token address of the token to approve.
            amount (int): Amount of tokens to approve in wei.
            chainId (int): Chain ID of the blockchain network.
            **kwargs: optional kwargs for the tool with args schema defined in EnsoGetApproveInput.

        Returns:
            Tuple[EnsoBroadcastWalletApproveOutput, EnsoBroadcastWalletApproveArtifact]: The list of approve transaction output or an error message.
        """
        url = f"{base_url}/api/v1/wallet/approve"
        context = self.get_context()
        api_token = self.get_api_token(context)
        account = await self.get_account(context)

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        from_address = account.address

        params = EnsoWalletApproveInput(
            tokenAddress=tokenAddress,
            amount=amount,
            chainId=chainId,
        )

        if kwargs.get("routingStrategy"):
            params.routingStrategy = kwargs["routingStrategy"]

        params = params.model_dump(exclude_none=True)

        params["fromAddress"] = from_address

        with httpx.Client() as client:
            try:
                # Send the GET request
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()

                # Map the response JSON into the WalletApproveTransaction model
                json_dict = response.json()
                content = EnsoWalletApproveOutput(**json_dict)
                artifact = EnsoWalletApproveArtifact(**json_dict)

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
                    artifact.txHash = tx_hash
                else:
                    # For now, return without executing the transaction if no tx data
                    artifact.txHash = "0x0000000000000000000000000000000000000000000000000000000000000000"

                # Return the parsed response
                return (content, artifact)
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
