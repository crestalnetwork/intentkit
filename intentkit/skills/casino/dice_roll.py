"""Quantum dice rolling skill using QRandom API."""

import logging
from typing import Type

try:
    import httpx
except ImportError:
    raise ImportError(
        "httpx is required for Casino skills. Install it with: pip install httpx"
    )
from pydantic import BaseModel, Field

from intentkit.skills.casino.base import CasinoBaseTool
from intentkit.skills.casino.utils import (
    ENDPOINTS,
    RATE_LIMITS,
    get_dice_visual,
    validate_dice_count,
)

NAME = "casino_dice_roll"
PROMPT = (
    "Roll quantum random dice using true quantum randomness. "
    "Can roll multiple 6-sided dice at once for games."
)

logger = logging.getLogger(__name__)


class CasinoDiceRollInput(BaseModel):
    """Input for CasinoDiceRoll tool."""

    dice_count: int = Field(default=1, description="Number of dice to roll (1-10)")


class CasinoDiceRoll(CasinoBaseTool):
    """Tool for rolling quantum random dice.

    This tool uses the QRandom API to generate truly random dice rolls
    using quantum randomness.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = CasinoDiceRollInput

    async def _arun(self, dice_count: int = 1, **kwargs) -> dict:
        try:
            context = self.get_context()

            # Apply rate limit using built-in user_rate_limit method
            rate_config = RATE_LIMITS["dice_roll"]
            await self.user_rate_limit(
                context.user_id or context.agent_id,
                rate_config["max_requests"],
                rate_config["interval"] // 60,  # Convert to minutes
                "dice_roll",
            )

            # Validate dice count
            dice_count = validate_dice_count(dice_count)

            # Build API URL
            url = ENDPOINTS["dice_roll"]
            params = {"n": dice_count}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()

                    dice_results = data.get("dice", [])
                    total = sum(dice_results)

                    # Generate dice emoji representation
                    dice_visual = get_dice_visual(dice_results)

                    return {
                        "success": True,
                        "dice_results": dice_results,
                        "dice_visual": dice_visual,
                        "total": total,
                        "dice_count": len(dice_results),
                        "quantum_signature": data.get("signature", ""),
                        "quantum_id": data.get("id", ""),
                        "message": f"Rolled {len(dice_results)} dice: {' '.join(dice_visual)} "
                        f"(Total: {total})",
                    }
                else:
                    logger.error(f"QRandom API error: {response.status_code}")
                    return {"success": False, "error": "Failed to roll dice"}

        except Exception as e:
            logger.error(f"Error rolling dice: {str(e)}")
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
