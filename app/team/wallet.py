"""Team API: Crypto Wallets — wallets owned at the team level.

Wallets belong to the team, never to an agent; agents are only authorized to
use one via ``Agent.wallet_id``. Members can list wallets; only admins can
create them. Provider payloads (private keys, Privy ids) are never returned —
``TeamWallet.wallet_data`` is excluded from serialization.
"""

import logging

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from intentkit.core.team.wallet import create_team_wallet
from intentkit.models.wallet import TeamWallet

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
    network_id: str | None = Field(
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
        network_id=body.network_id,
        readonly_address=body.readonly_address,
        weekly_spending_limit=body.weekly_spending_limit,
    )
