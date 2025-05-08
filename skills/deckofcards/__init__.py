"""Deck of Cards skills."""

from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.deckofcards.add_to_pile import AddToPile
from skills.deckofcards.base import DeckOfCardsBaseSkill
from skills.deckofcards.draw_cards import DrawCards
from skills.deckofcards.draw_from_pile import DrawFromPile
from skills.deckofcards.list_piles import ListPiles
from skills.deckofcards.shuffle_deck import ShuffleDeck

# Cache skills at the system level, because they are stateless
_cache: dict[str, DeckOfCardsBaseSkill] = {}


class SkillStates(TypedDict):
    shuffle_deck: SkillState


class Config(SkillConfig):
    """Configuration for Deck of Cards skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[DeckOfCardsBaseSkill]:
    """Get all Deck of Cards skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [get_deckofcards_skill(name, store) for name in available_skills]


def get_deckofcards_skill(
    name: str,
    store: SkillStoreABC,
) -> DeckOfCardsBaseSkill:
    """Get a Deck of Cards skill by name."""
    if name not in _cache:
        if name == "shuffle_deck":
            _cache[name] = ShuffleDeck(skill_store=store)
        elif name == "draw_cards":
            _cache[name] = DrawCards(skill_store=store)
        elif name == "add_to_pile":
            _cache[name] = AddToPile(skill_store=store)
        elif name == "draw_from_pile":
            _cache[name] = DrawFromPile(skill_store=store)
        elif name == "list_piles":
            _cache[name] = ListPiles(skill_store=store)
        else:
            raise ValueError(f"Unknown Deck of Cards skill: {name}")
    return _cache[name]
