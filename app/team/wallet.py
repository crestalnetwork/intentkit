"""Team API: Crypto Wallets — wallets owned at the team level.

Wallets belong to the team, never to an agent. Web3 tools pick a wallet by
address from the team's pool at call time. Members can list wallets; only
admins can create, rename, delete, or adjust them. Provider payloads
(private keys, Privy ids) are never returned — ``TeamWallet.wallet_data``
is excluded from serialization.
"""

import logging

from fastapi import APIRouter, Body, Depends, Path, Response
from pydantic import BaseModel, Field

from intentkit.core.team.wallet import (
    create_team_wallet,
    delete_team_wallet,
    set_wallet_safe_token_spending_limit,
    update_team_wallet,
)
from intentkit.models.wallet import NetworkIdLiteral, TeamWallet

from app.team.auth import verify_team_admin, verify_team_member

logger = logging.getLogger(__name__)

team_wallet_router = APIRouter()


@team_wallet_router.get(
    "/teams/{team_id}/wallets",
    response_model=list[TeamWallet],
    operation_id="team_list_wallets",
    summary="List team wallets (Team)",
    tags=["Wallet"],
)
async def list_wallets(
    auth: tuple[str, str] = Depends(verify_team_member),
) -> list[TeamWallet]:
    """List all crypto wallets owned by the team."""
    _user_id, team_id = auth
    return await TeamWallet.list_for_team(team_id)


class WalletCreateRequest(BaseModel):
    """Parameters for provisioning a new team wallet."""

    name: str = Field(
        min_length=1, max_length=50, description="Display name, unique within the team"
    )
    wallet_provider: str = Field(
        description="cdp | native | readonly | safe | privy",
    )
    default_network_id: NetworkIdLiteral | None = Field(
        default=None, description="Default network (defaults to base-mainnet)"
    )
    readonly_address: str | None = Field(
        default=None, description="Watched address (readonly wallets only)"
    )
    weekly_spending_limit: float | None = Field(
        default=None, ge=0.0, description="Weekly USDC spending limit (safe only)"
    )


@team_wallet_router.post(
    "/teams/{team_id}/wallets",
    response_model=TeamWallet,
    status_code=201,
    operation_id="team_create_wallet",
    summary="Create a team wallet (Team)",
    tags=["Wallet"],
)
async def create_wallet(
    body: WalletCreateRequest = Body(...),
    auth: tuple[str, str] = Depends(verify_team_admin),
) -> TeamWallet:
    """Provision a new wallet owned by the team."""
    user_id, team_id = auth
    return await create_team_wallet(
        team_id=team_id,
        name=body.name,
        wallet_provider=body.wallet_provider,
        created_by=user_id,
        default_network_id=body.default_network_id,
        readonly_address=body.readonly_address,
        weekly_spending_limit=body.weekly_spending_limit,
    )


class WalletUpdateRequest(BaseModel):
    """Update a wallet's mutable settings; omitted fields stay unchanged."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="New display name, unique within the team",
    )
    default_network_id: NetworkIdLiteral | None = Field(
        default=None, description="Default network for tools using this wallet"
    )


@team_wallet_router.patch(
    "/teams/{team_id}/wallets/{wallet_id}",
    response_model=TeamWallet,
    operation_id="team_update_wallet",
    summary="Update a team wallet (Team)",
    tags=["Wallet"],
)
async def update_wallet(
    wallet_id: str = Path(..., description="Wallet ID"),
    body: WalletUpdateRequest = Body(...),
    auth: tuple[str, str] = Depends(verify_team_admin),
) -> TeamWallet:
    """Update a team wallet's name and/or default network."""
    _user_id, team_id = auth
    return await update_team_wallet(
        team_id,
        wallet_id,
        name=body.name,
        default_network_id=body.default_network_id,
    )


@team_wallet_router.delete(
    "/teams/{team_id}/wallets/{wallet_id}",
    status_code=204,
    operation_id="team_delete_wallet",
    summary="Delete a team wallet (Team)",
    tags=["Wallet"],
)
async def delete_wallet(
    wallet_id: str = Path(..., description="Wallet ID"),
    auth: tuple[str, str] = Depends(verify_team_admin),
) -> Response:
    """Delete a team wallet.

    Funds are not swept — empty the wallet first. Refused (409) for the
    team's last wallet while live agents have web3 tools configured.
    """
    _user_id, team_id = auth
    await delete_team_wallet(team_id, wallet_id)
    return Response(status_code=204)


class WalletSpendingLimitRequest(BaseModel):
    """Set a token spending limit on a Safe wallet."""

    token_address: str = Field(description="ERC20 token contract address")
    spending_limit: float = Field(ge=0.0, description="Spending limit in token units")


@team_wallet_router.put(
    "/teams/{team_id}/wallets/{wallet_id}/spending-limit",
    operation_id="team_set_wallet_spending_limit",
    summary="Set a Safe wallet token spending limit (Team)",
    tags=["Wallet"],
)
async def set_wallet_spending_limit(
    wallet_id: str = Path(..., description="Wallet ID"),
    body: WalletSpendingLimitRequest = Body(...),
    auth: tuple[str, str] = Depends(verify_team_admin),
) -> dict:
    """Set a token spending limit on the team's Safe wallet."""
    _user_id, team_id = auth
    return await set_wallet_safe_token_spending_limit(
        team_id, wallet_id, body.token_address, body.spending_limit
    )
