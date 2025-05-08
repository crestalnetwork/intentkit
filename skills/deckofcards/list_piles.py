import httpx
from .base import DeckOfCardsBaseSkill

class ListPiles(DeckOfCardsBaseSkill):
    """Skill to list all piles and their contents in a deck."""
    
    name = "list_piles"
    description = "View existing piles and their contents in the deck"
    
    async def _arun(self, deck_id: str) -> str:
        """
        List all piles and their contents.
        
        Args:
            deck_id: ID of the deck
        
        Returns:
            str: Formatted response containing pile information and contents
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://deckofcardsapi.com/api/deck/{deck_id}/pile/list/"
                )
                response.raise_for_status()
                data = response.json()

                if not data['success']:
                    return "Error: Failed to list piles"

                result = [
                    "Piles Listed Successfully",
                    f"Deck ID: {data['deck_id']}",
                    f"Cards Remaining in Deck: {data['remaining']}",
                    "",
                    "Pile Contents:"
                ]

                # Add information about each pile
                for pile_name, pile_info in data['piles'].items():
                    result.append(f"\n{pile_name}:")
                    result.append(f"- Cards Remaining: {pile_info['remaining']}")
                    
                    # Add card details if available
                    if 'cards' in pile_info:
                        result.append("- Cards:")
                        for card in pile_info['cards']:
                            result.extend([
                                f"  * {card['value']} of {card['suit']}",
                                f"    Image: {card['image']}"
                            ])

                return "\n".join(result)
                
        except httpx.HTTPError as e:
            return f"Error listing piles: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}" 