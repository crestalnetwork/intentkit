from skills.venice_image.image_generation.image_generation_base import (
    VeniceImageGenerationBaseTool,
)
from skills.venice_image.image_generation.image_generation_input import STYLE_PRESETS


class ImageGenerationVeniceSD35(VeniceImageGenerationBaseTool):
    """
    Tool for generating images using Venice AI's interface to Stable Diffusion 3.5 Large.
    Developed by Stability AI, using MMDiT architecture. Good for art and design.
    """

    # --- Model Specific Configuration ---
    name: str = "image_generation_venice_sd35"
    description: str = (
        "Generate images using Stability AI's Stable Diffusion 3.5 Large model (via Venice AI).\n"
        "Ideal for artworks, design processes, and educational use. Not for factual representations.\n"
        "Provide a text prompt describing the image (up to 1500 chars).\n"
        f"Optionally specify a style preset from the list: {', '.join(STYLE_PRESETS)}.\n"
        "Supports dimensions up to 2048x2048 (multiple of 16).\n"
        "Use must comply with Stability AI's Acceptable Use Policy."
    )
    # Use the specific ID provided by Venice, assuming it matches the name
    model_id: str = "venice-sd35"

    # args_schema and _arun are inherited from VeniceImageGenerationBaseTool
