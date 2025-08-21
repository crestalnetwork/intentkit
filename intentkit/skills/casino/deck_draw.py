"""Card drawing skill using Deck of Cards API."""

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
    CURRENT_DECK_KEY,
    DECK_STORAGE_KEY,
    ENDPOINTS,
    RATE_LIMITS,
    format_card_info,
    validate_card_count,
)

NAME = "casino_deck_draw"
PROMPT = (
    "Draw cards from the current deck. If no deck exists, a new one will be created. "
    "Returns detailed card information including images."
)

logger = logging.getLogger(__name__)


class CasinoDeckDrawInput(BaseModel):
    """Input for CasinoDeckDraw tool."""

    count: int = Field(default=1, description="Number of cards to draw (1-10)")


class CasinoDeckDraw(CasinoBaseTool):
    """Tool for drawing cards from a deck.

    This tool uses the Deck of Cards API to draw cards from the current deck.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = CasinoDeckDrawInput

    async def _arun(self, count: int = 1, **kwargs) -> dict:
        try:
            context = self.get_context()

            # Apply rate limit using built-in user_rate_limit method
            rate_config = RATE_LIMITS["deck_draw"]
            await self.user_rate_limit(
                context.user_id or context.agent_id,
                rate_config["max_requests"],
                rate_config["interval"] // 60,  # Convert to minutes
                "deck_draw",
            )

            # Validate count
            count = validate_card_count(count)

            # Get current deck info
            deck_info = await self.skill_store.get_agent_skill_data(
                context.agent_id, DECK_STORAGE_KEY, CURRENT_DECK_KEY
            )

            deck_id = "new"  # Default to new deck
            if deck_info and deck_info.get("deck_id"):
                deck_id = deck_info["deck_id"]

            # Build API URL
            url = ENDPOINTS["deck_draw"].format(deck_id=deck_id)
            params = {"count": count}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()

                    if data.get("success"):
                        # Update deck info
                        if deck_id == "new":
                            deck_info = {
                                "deck_id": data["deck_id"],
                                "deck_count": 1,
                                "jokers_enabled": False,
                                "remaining": data["remaining"],
                                "shuffled": True,
                            }
                        else:
                            deck_info["remaining"] = data["remaining"]

                        await self.skill_store.save_agent_skill_data(
                            context.agent_id,
                            DECK_STORAGE_KEY,
                            CURRENT_DECK_KEY,
                            deck_info,
                        )

                        # Format card information with images
                        cards = [
                            format_card_info(card) for card in data.get("cards", [])
                        ]

                        return {
                            "success": True,
                            "cards_drawn": cards,
                            "remaining_cards": data["remaining"],
                            "deck_id": data["deck_id"],
                            "message": f"Drew {len(cards)} card{'s' if len(cards) > 1 else ''} "
                            f"({data['remaining']} remaining)",
                        }
                    else:
                        return {"success": False, "error": "Failed to draw cards"}
                else:
                    logger.error(f"Deck API error: {response.status_code}")
                    return {"success": False, "error": "Failed to draw cards"}

        except Exception as e:
            logger.error(f"Error drawing cards: {str(e)}")
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
