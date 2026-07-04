"""Agent wallet binding validation.

Agents no longer own or provision wallets. A wallet is a team resource
(``intentkit.models.wallet``); ``Agent.wallet_id`` merely authorizes the
agent to use one of its team's wallets. This module validates that binding
on agent create/update.
"""

import logging

from intentkit.models.wallet import TeamWallet, wallet_owner_team
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def validate_wallet_binding(
    wallet_id: str | None, team_id: str | None
) -> TeamWallet | None:
    """Ensure a wallet_id points at a wallet of the given team.

    Returns the bound wallet, or None when no wallet is bound.

    Raises:
        IntentKitAPIError: If the wallet does not exist or belongs to
            another team.
    """
    if not wallet_id:
        return None

    wallet = await TeamWallet.get(wallet_id)
    if wallet is None:
        raise IntentKitAPIError(
            400,
            "WalletNotFound",
            f"Wallet '{wallet_id}' does not exist.",
        )

    expected_team = wallet_owner_team(team_id)
    if wallet.team_id != expected_team:
        raise IntentKitAPIError(
            400,
            "WalletNotOwnedByTeam",
            "Agents can only use wallets owned by their own team.",
        )

    return wallet
