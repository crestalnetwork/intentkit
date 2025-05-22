from typing import List

import httpx

from .base import DeckOfCardsBaseSkill


class AddToPile(DeckOfCardsBaseSkill):
    """Skill to add cards to a named pile."""

    name = "add_to_pile"
    description = "Add specified cards to a named pile in the deck"

    async def _arun(self, deck_id: str, pile_name: str, cards: List[str]) -> str:
        """
        Add cards to a named pile.

        Args:
            deck_id: ID of the deck
            pile_name: Name of the pile to add cards to
            cards: List of card codes to add (e.g., ["AS", "2S"])

        Returns:
            str: Formatted response containing pile information
        """
        try:
            # Convert list of cards to comma-separated string
            cards_str = ",".join(cards)

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://deckofcardsapi.com/api/deck/{deck_id}/pile/{pile_name}/add/",
                    params={"cards": cards_str},
                )
                response.raise_for_status()
                data = response.json()

                if not data["success"]:
                    return "Error: Failed to add cards to pile"

                result = [
                    "Cards Added to Pile Successfully",
                    f"Deck ID: {data['deck_id']}",
                    f"Cards Remaining in Deck: {data['remaining']}",
                    "",
                    "Pile Status:",
                ]

                # Add information about each pile
                for pile_name, pile_info in data["piles"].items():
                    result.append(f"- {pile_name}: {pile_info['remaining']} cards")

                return "\n".join(result)

        except httpx.HTTPError as e:
            return f"Error adding cards to pile: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
