from intentkit.skills.venice_image.image_generation.image_generation_base import (
    VeniceImageGenerationBaseTool,
)
from intentkit.skills.venice_image.image_generation.image_generation_input import (
    STYLE_PRESETS,
)


class ImageGenerationPonyRealism(VeniceImageGenerationBaseTool):
    """
    Tool for generating images using the Pony Realism model via Venice AI.
    Focused on high-detail, realistic images, especially anime/character designs. Uses Danbooru tags.
    """

    # --- Model Specific Configuration ---
    name: str = "venice_image_generation_pony_realism"
    description: str = (
        "Generate images using the Pony Realism model (via Venice AI).\n"
        "Creates high-detail, realistic images, good for anime/character designs. Benefits from Danbooru tags (e.g., 'score_9', 'female'/'male').\n"
        "Provide a text prompt describing the image (up to 1500 chars).\n"
        f"Optionally specify a style preset from the list: {', '.join(STYLE_PRESETS)}.\n"
        "Supports dimensions up to 2048x2048 (multiple of 8). Marked as 'most_uncensored'."
    )
    model_id: str = "pony-realism"

    # args_schema and _arun are inherited from VeniceImageGenerationBaseTool
