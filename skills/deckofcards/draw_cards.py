import httpx

from .base import DeckOfCardsBaseSkill


class DrawCards(DeckOfCardsBaseSkill):
    """Skill to draw cards from a deck."""

    name = "draw_cards"
    description = "Draw a specified number of cards from a deck"

    async def _arun(self, deck_id: str, count: int = 1) -> str:
        """
        Draw cards from a deck.

        Args:
            deck_id: ID of the deck to draw from
            count: Number of cards to draw (default: 1)
            params: Additional parameters (unused)

        Returns:
            str: Formatted response containing drawn cards information
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://deckofcardsapi.com/api/deck/{deck_id}/draw/",
                    params={"count": count},
                )
                response.raise_for_status()
                data = response.json()

                if not data["success"]:
                    return "Error: Failed to draw cards"

                result = [
                    "Cards Drawn Successfully",
                    f"Deck ID: {data['deck_id']}",
                    f"Cards Remaining: {data['remaining']}",
                    "",
                    "Drawn Cards:",
                ]

                for card in data["cards"]:
                    result.extend(
                        [
                            f"- {card['value']} of {card['suit']}",
                            f"  Image: {card['image']}",
                        ]
                    )

                return "\n".join(result)

        except httpx.HTTPError as e:
            return f"Error drawing cards: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
