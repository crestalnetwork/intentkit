from skills.venice_image.image_generation.image_generation_base import (
    VeniceImageGenerationBaseTool,
)
from skills.venice_image.image_generation.image_generation_input import STYLE_PRESETS


class ImageGenerationStableDiffusion35(VeniceImageGenerationBaseTool):
    """
    Tool for generating images using Venice AI's interface to Stable Diffusion 3.5 Large (alternative ID).
    Developed by Stability AI, using MMDiT architecture. Good for art and design.
    """

    # --- Model Specific Configuration ---
    name: str = "image_generation_stable_diffusion_3_5"  # Different skill name
    description: str = (
        "Generate images using Stability AI's Stable Diffusion 3.5 Large model (alternative ID via Venice AI).\n"
        "Ideal for artworks, design processes, and educational use. Not for factual representations.\n"
        "Provide a text prompt describing the image (up to 1500 chars).\n"
        f"Optionally specify a style preset from the list: {', '.join(STYLE_PRESETS)}.\n"
        "Supports dimensions up to 2048x2048 (multiple of 16).\n"
        "Use must comply with Stability AI's Acceptable Use Policy."
    )
    # Use the specific ID provided by Venice
    model_id: str = "stable-diffusion-3.5"  # Different model ID

    # args_schema and _arun are inherited from VeniceImageGenerationBaseTool
