from skills.venice_image.image_generation.image_generation_base import (
    VeniceImageGenerationBaseTool,
)
from skills.venice_image.image_generation.image_generation_input import STYLE_PRESETS


class ImageGenerationFluentlyXL(VeniceImageGenerationBaseTool):
    """
    Tool for generating images using the Fluently-XL model via Venice AI.
    Known for aesthetics, lighting, realism, and correct anatomy.
    """

    # --- Model Specific Configuration ---
    name: str = "image_generation_fluently_xl"
    description: str = (
        "Generate images using the Fluently-XL model (via Venice AI).\n"
        "Aims for improved aesthetics, lighting, realism, and anatomy. Good for professional-quality images.\n"
        "Provide a text prompt describing the image (up to 1500 chars).\n"
        f"Optionally specify a style preset from the list: {', '.join(STYLE_PRESETS)}.\n"
        "Supports dimensions up to 2048x2048 (multiple of 8)."
    )
    model_id: str = "fluently-xl"

    # args_schema and _arun are inherited from VeniceImageGenerationBaseTool
