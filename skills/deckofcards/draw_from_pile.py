from typing import List

import httpx

from .base import DeckOfCardsBaseSkill


class DrawFromPile(DeckOfCardsBaseSkill):
    """Skill to draw cards from a named pile."""

    name = "draw_from_pile"
    description = "Draw specified cards from a named pile in the deck"

    async def _arun(self, deck_id: str, pile_name: str, cards: List[str]) -> str:
        """
        Draw cards from a named pile.

        Args:
            deck_id: ID of the deck
            pile_name: Name of the pile to draw from
            cards: List of card codes to draw (e.g., ["AS", "2S"])

        Returns:
            str: Formatted response containing drawn cards and pile information
        """
        try:
            # Convert list of cards to comma-separated string
            cards_str = ",".join(cards)

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://deckofcardsapi.com/api/deck/{deck_id}/pile/{pile_name}/draw/",
                    params={"cards": cards_str},
                )
                response.raise_for_status()
                data = response.json()

                if not data["success"]:
                    return "Error: Failed to draw cards from pile"

                result = [
                    "Cards Drawn from Pile Successfully",
                    f"Deck ID: {data['deck_id']}",
                    f"Cards Remaining in Deck: {data['remaining']}",
                    "",
                    "Pile Status:",
                ]

                # Add information about each pile
                for pile_name, pile_info in data["piles"].items():
                    result.append(f"- {pile_name}: {pile_info['remaining']} cards")

                # Add information about drawn cards
                if "cards" in data:
                    result.extend(["", "Drawn Cards:"])
                    for card in data["cards"]:
                        result.extend(
                            [
                                f"- {card['value']} of {card['suit']}",
                                f"  Image: {card['image']}",
                            ]
                        )

                return "\n".join(result)

        except httpx.HTTPError as e:
            return f"Error drawing cards from pile: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
