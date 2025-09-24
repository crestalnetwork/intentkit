from typing import Literal, Tuple, Type

import httpx
from langchain.tools.base import ToolException
from pydantic import BaseModel, Field

from .base import EnsoBaseTool, base_url


class EnsoGetBalancesInput(BaseModel):
    """Input model for retrieving wallet balances."""

    chainId: int | None = Field(None, description="Chain ID of the blockchain network")


class WalletBalance(BaseModel):
    token: str | None = Field(None, description="The address of the token")
    amount: str | None = Field(None, description="The unformatted balance of the token")
    decimals: int | None = Field(None, ge=0, description="The number of decimals")
    price: float | None = Field(None, description="Price of the token in usd")


class EnsoGetBalancesOutput(BaseModel):
    """Output model for retrieving wallet balances."""

    res: list[WalletBalance] | None = Field(
        None, description="The wallet's balances along with token details."
    )


class EnsoGetWalletBalances(EnsoBaseTool):
    """Retrieve token balances of a wallet on a specified blockchain network."""

    name: str = "enso_get_wallet_balances"
    description: str = (
        "Retrieve token balances of a wallet on a specified blockchain network."
    )
    args_schema: Type[BaseModel] = EnsoGetBalancesInput

    async def _arun(
        self,
        chainId: int | None = None,
        **_: object,
    ) -> EnsoGetBalancesOutput:
        context = self.get_context()
        resolved_chain_id = self.resolve_chain_id(context, chainId)
        api_token = self.get_api_token(context)
        wallet_address = await self.get_wallet_address(context)

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        params = EnsoGetBalancesInput(chainId=resolved_chain_id).model_dump(
            exclude_none=True
        )
        params["eoaAddress"] = wallet_address
        params["useEoa"] = True

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/wallet/balances",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                json_dict = response.json()[:20]
                res = [WalletBalance(**item) for item in json_dict]
                return EnsoGetBalancesOutput(res=res)
            except httpx.RequestError as req_err:
                raise ToolException("request error from Enso API") from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException("http error from Enso API") from http_err
            except Exception as exc:  # pragma: no cover - defensive
                raise ToolException(f"error from Enso API: {exc}") from exc


class EnsoGetApprovalsInput(BaseModel):
    """Input model for retrieving wallet approvals."""

    chainId: int | None = Field(None, description="Chain ID of the blockchain network")
    routingStrategy: Literal["ensowallet", "router", "delegate"] | None = Field(
        None, description="Routing strategy to use"
    )


class WalletAllowance(BaseModel):
    token: str | None = Field(None, description="The token address")
    allowance: str | None = Field(None, description="The amount of tokens approved")
    spender: str | None = Field(None, description="The spender address")


class EnsoGetApprovalsOutput(BaseModel):
    """Output model for retrieving wallet approvals."""

    res: list[WalletAllowance] | None = Field(
        None, description="Response containing the list of token approvals."
    )


class EnsoGetWalletApprovals(EnsoBaseTool):
    """Retrieve token spend approvals for a wallet on a specified blockchain network."""

    name: str = "enso_get_wallet_approvals"
    description: str = (
        "Retrieve token spend approvals for a wallet on a specified blockchain network."
    )
    args_schema: Type[BaseModel] = EnsoGetApprovalsInput

    async def _arun(
        self,
        chainId: int | None = None,
        routingStrategy: Literal["ensowallet", "router", "delegate"] | None = None,
        **_: object,
    ) -> EnsoGetApprovalsOutput:
        context = self.get_context()
        resolved_chain_id = self.resolve_chain_id(context, chainId)
        api_token = self.get_api_token(context)
        wallet_address = await self.get_wallet_address(context)

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        params = EnsoGetApprovalsInput(
            chainId=resolved_chain_id,
            routingStrategy=routingStrategy,
        ).model_dump(exclude_none=True)
        params["fromAddress"] = wallet_address

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/wallet/approvals",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                json_dict = response.json()[:50]
                res = [WalletAllowance(**item) for item in json_dict]
                return EnsoGetApprovalsOutput(res=res)
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Enso API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Enso API: {http_err}"
                ) from http_err
            except Exception as exc:  # pragma: no cover - defensive
                raise ToolException(f"error from Enso API: {exc}") from exc


class EnsoWalletApproveInput(BaseModel):
    """Input model for approving token spend for the wallet."""

    tokenAddress: str = Field(description="ERC20 token address of the token to approve")
    amount: int = Field(description="Amount of tokens to approve in wei")
    chainId: int | None = Field(None, description="Chain ID of the blockchain network")
    routingStrategy: Literal["ensowallet", "router", "delegate"] | None = Field(
        None, description="Routing strategy to use"
    )


class EnsoWalletApproveOutput(BaseModel):
    """Output model for approve token for the wallet."""

    gas: str | None = Field(None, description="The gas estimate for the transaction")
    token: str | None = Field(None, description="The token address to approve")
    amount: str | None = Field(None, description="The amount of tokens to approve")
    spender: str | None = Field(None, description="The spender address to approve")


class EnsoWalletApproveArtifact(BaseModel):
    """Artifact returned after broadcasting an approval transaction."""

    tx: object | None = Field(
        None, description="The transaction object to use in `ethers`"
    )
    txHash: str | None = Field(None, description="The transaction hash")


class EnsoWalletApprove(EnsoBaseTool):
    """Broadcast an ERC20 token spending approval transaction."""

    name: str = "enso_wallet_approve"
    description: str = (
        "This tool is used specifically for broadcasting a ERC20 token spending approval transaction to the "
        "network. It should only be used when the user explicitly requests to broadcast an approval transaction "
        "with a specific amount for a certain token."
    )
    args_schema: Type[BaseModel] = EnsoWalletApproveInput
    response_format: str = "content_and_artifact"

    async def _arun(
        self,
        tokenAddress: str,
        amount: int,
        chainId: int | None = None,
        routingStrategy: Literal["ensowallet", "router", "delegate"] | None = None,
        **_: object,
    ) -> Tuple[EnsoWalletApproveOutput, EnsoWalletApproveArtifact]:
        context = self.get_context()
        resolved_chain_id = self.resolve_chain_id(context, chainId)
        api_token = self.get_api_token(context)
        wallet_address = await self.get_wallet_address(context)

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        params = EnsoWalletApproveInput(
            tokenAddress=tokenAddress,
            amount=amount,
            chainId=resolved_chain_id,
            routingStrategy=routingStrategy,
        ).model_dump(exclude_none=True)
        params["fromAddress"] = wallet_address

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/wallet/approve",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()

                json_dict = response.json()
                content = EnsoWalletApproveOutput(**json_dict)
                artifact = EnsoWalletApproveArtifact(**json_dict)

                wallet_provider = await self.get_wallet_provider(context)
                tx_data = json_dict.get("tx", {})
                if tx_data:
                    tx_hash = wallet_provider.send_transaction(
                        {
                            "to": tx_data.get("to"),
                            "data": tx_data.get("data", "0x"),
                            "value": tx_data.get("value", 0),
                            "from": wallet_address,
                        }
                    )

                    wallet_provider.wait_for_transaction_receipt(tx_hash)
                    artifact.txHash = tx_hash
                else:
                    artifact.txHash = "0x0000000000000000000000000000000000000000000000000000000000000000"

                return (content, artifact)
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Enso API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Enso API: {http_err}"
                ) from http_err
            except Exception as exc:  # pragma: no cover - defensive
                raise ToolException(f"error from Enso API: {exc}") from exc
