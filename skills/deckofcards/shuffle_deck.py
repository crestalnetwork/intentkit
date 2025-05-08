import httpx
from .base import DeckOfCardsBaseSkill

class ShuffleDeck(DeckOfCardsBaseSkill):
    """Skill to shuffle a new deck of cards."""
    
    name = "shuffle_deck"
    description = "Initialize and shuffle a new deck of cards"
    
    async def _arun(self, deck_count: int = 1) -> str:
        """
        Shuffle a new deck of cards.
        
        Args:
            deck_count: Number of decks to shuffle (default: 1)
            params: Additional parameters (unused)
        
        Returns:
            str: Formatted response containing deck information
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://deckofcardsapi.com/api/deck/new/shuffle/",
                    params={"deck_count": deck_count}
                )
                response.raise_for_status()
                data = response.json()

                result = [
                    "Deck Shuffled Successfully",
                    f"Deck ID: {data['deck_id']}",
                    f"Cards Remaining: {data['remaining']}",
                    f"Status: {'Shuffled' if data['shuffled'] else 'Not Shuffled'}",
                    "",
                    "You can now use this deck for drawing cards or other operations."
                ]

                return "\n".join(result)
                
        except httpx.HTTPError as e:
            return f"Error shuffling deck: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}" 