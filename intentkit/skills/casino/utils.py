"""
Casino Skills Utilities

Common constants, URLs, and helper functions for Casino skills.
"""

# API URLs
DECK_OF_CARDS_API_BASE = "https://www.deckofcardsapi.com/api/deck"
QRANDOM_API_BASE = "https://qrandom.io/api/random"

# API Endpoints
ENDPOINTS = {
    "deck_new_shuffle": f"{DECK_OF_CARDS_API_BASE}/new/shuffle/",
    "deck_draw": f"{DECK_OF_CARDS_API_BASE}/{{deck_id}}/draw/",
    "dice_roll": f"{QRANDOM_API_BASE}/dice",
}

# Rate Limits (requests per minute)
RATE_LIMITS = {
    "deck_shuffle": {"max_requests": 20, "interval": 60},
    "deck_draw": {"max_requests": 30, "interval": 60},
    "dice_roll": {"max_requests": 15, "interval": 60},
}

# Storage Keys
DECK_STORAGE_KEY = "casino_deck"
CURRENT_DECK_KEY = "current_deck"

# Dice visual representation
DICE_EMOJI = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

# Card back image URL for display
CARD_BACK_IMAGE = "https://www.deckofcardsapi.com/static/img/back.png"

# Validation limits
MAX_DECK_COUNT = 6
MIN_DECK_COUNT = 1
MAX_CARDS_DRAW = 10
MIN_CARDS_DRAW = 1
MAX_DICE_COUNT = 10
MIN_DICE_COUNT = 1


def get_dice_visual(dice_results: list[int]) -> list[str]:
    """Convert dice numbers to emoji representation.

    Args:
        dice_results: List of dice roll results (1-6)

    Returns:
        List of dice emoji strings
    """
    return [DICE_EMOJI[result - 1] for result in dice_results if 1 <= result <= 6]


def validate_deck_count(count: int) -> int:
    """Validate and normalize deck count.

    Args:
        count: Requested deck count

    Returns:
        Normalized deck count within valid range
    """
    return max(MIN_DECK_COUNT, min(MAX_DECK_COUNT, count))


def validate_card_count(count: int) -> int:
    """Validate and normalize card draw count.

    Args:
        count: Requested card count

    Returns:
        Normalized card count within valid range
    """
    return max(MIN_CARDS_DRAW, min(MAX_CARDS_DRAW, count))


def validate_dice_count(count: int) -> int:
    """Validate and normalize dice count.

    Args:
        count: Requested dice count

    Returns:
        Normalized dice count within valid range
    """
    return max(MIN_DICE_COUNT, min(MAX_DICE_COUNT, count))


def format_card_info(card: dict) -> dict:
    """Format card information for consistent output.

    Args:
        card: Raw card data from Deck of Cards API

    Returns:
        Formatted card information
    """
    return {
        "value": card["value"],
        "suit": card["suit"],
        "code": card["code"],
        "image": card["image"],
        "svg_image": card["images"]["svg"],
    }
