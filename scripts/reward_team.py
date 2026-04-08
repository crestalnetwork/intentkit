"""Add reward credits to a team account.

Usage: python -m scripts.reward_team <team_id> <amount> [note]

Example:
    python -m scripts.reward_team team_abc123 1000 "Initial credits for onboarding"
"""

import asyncio
import sys
from decimal import Decimal

from epyxid import XID


async def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.reward_team <team_id> <amount> [note]")
        sys.exit(1)

    team_id = sys.argv[1]
    try:
        amount = Decimal(sys.argv[2])
    except Exception:
        print(f"Invalid amount: {sys.argv[2]}")
        sys.exit(1)

    if amount <= 0:
        print("Amount must be positive")
        sys.exit(1)

    note = sys.argv[3] if len(sys.argv) > 3 else "Manual team reward"
    upstream_tx_id = f"manual_reward_{XID()}"

    from intentkit.config.config import config
    from intentkit.config.db import get_session, init_db
    from intentkit.core.credit.reward import reward

    await init_db(**config.db)

    async with get_session() as session:
        account = await reward(
            session,
            team_id=team_id,
            amount=amount,
            upstream_tx_id=upstream_tx_id,
            note=note,
        )
        print(f"Rewarded {amount} credits to team {team_id}")
        print(f"  Reward credits: {account.reward_credits}")
        print(f"  Permanent credits: {account.credits}")
        print(f"  Free credits: {account.free_credits}")
        print(f"  Total balance: {account.balance}")


if __name__ == "__main__":
    asyncio.run(main())
