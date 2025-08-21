"""Deck shuffling skill using Deck of Cards API."""

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
    validate_deck_count,
)

NAME = "casino_deck_shuffle"
PROMPT = (
    "Create and shuffle a new deck of cards. You can specify the number of decks "
    "to use (default is 1) and optionally include jokers."
)

logger = logging.getLogger(__name__)


class CasinoDeckShuffleInput(BaseModel):
    """Input for CasinoDeckShuffle tool."""

    deck_count: int = Field(
        default=1, description="Number of decks to use (1-6, default 1)"
    )
    jokers_enabled: bool = Field(
        default=False, description="Whether to include jokers in the deck"
    )


class CasinoDeckShuffle(CasinoBaseTool):
    """Tool for creating and shuffling card decks.

    This tool uses the Deck of Cards API to create new shuffled decks.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = CasinoDeckShuffleInput

    async def _arun(
        self, deck_count: int = 1, jokers_enabled: bool = False, **kwargs
    ) -> dict:
        try:
            context = self.get_context()

            # Apply rate limit using built-in user_rate_limit method
            rate_config = RATE_LIMITS["deck_shuffle"]
            await self.user_rate_limit(
                context.user_id or context.agent_id,
                rate_config["max_requests"],
                rate_config["interval"] // 60,  # Convert to minutes
                "deck_shuffle",
            )

            # Validate deck count
            deck_count = validate_deck_count(deck_count)

            # Build API URL and parameters
            url = ENDPOINTS["deck_new_shuffle"]
            params = {"deck_count": deck_count}

            if jokers_enabled:
                params["jokers_enabled"] = "true"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()

                    # Store deck info for the agent
                    deck_info = {
                        "deck_id": data["deck_id"],
                        "deck_count": deck_count,
                        "jokers_enabled": jokers_enabled,
                        "remaining": data["remaining"],
                        "shuffled": data["shuffled"],
                    }

                    await self.skill_store.save_agent_skill_data(
                        context.agent_id, DECK_STORAGE_KEY, CURRENT_DECK_KEY, deck_info
                    )

                    return {
                        "success": True,
                        "deck_id": data["deck_id"],
                        "deck_count": deck_count,
                        "jokers_enabled": jokers_enabled,
                        "remaining_cards": data["remaining"],
                        "message": f"Created and shuffled {'a new deck' if deck_count == 1 else f'{deck_count} decks'} "
                        f"with {data['remaining']} cards"
                        + (" (including jokers)" if jokers_enabled else ""),
                    }
                else:
                    logger.error(f"Deck API error: {response.status_code}")
                    return {"success": False, "error": "Failed to create deck"}

        except Exception as e:
            logger.error(f"Error shuffling deck: {str(e)}")
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
