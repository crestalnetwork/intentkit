from intentkit.skills.venice_image.image_generation.image_generation_base import (
    VeniceImageGenerationBaseTool,
)
from intentkit.skills.venice_image.image_generation.image_generation_input import (
    STYLE_PRESETS,
)


class ImageGenerationLustifySDXL(VeniceImageGenerationBaseTool):
    """
    Tool for generating images using the Lustify SDXL model via Venice AI.
    A photorealistic SDXL checkpoint primarily focused on NSFW content, but can do SFW.
    """

    # --- Model Specific Configuration ---
    name: str = "venice_image_generation_lustify_sdxl"
    description: str = (
        "Generate images using the Lustify SDXL model (via Venice AI).\n"
        "A photorealistic SDXL model focused on NSFW scenes, but can generate SFW images (objects, animals, fantasy).\n"
        "Provide a text prompt describing the image (up to 1500 chars).\n"
        f"Optionally specify a style preset from the list: {', '.join(STYLE_PRESETS)}.\n"
        "Supports dimensions up to 2048x2048 (multiple of 8)."
    )
    model_id: str = "lustify-sdxl"

    # args_schema and _arun are inherited from VeniceImageGenerationBaseTool
