from skills.venice_image.image_generation.image_generation_base import (
    VeniceImageGenerationBaseTool,
)
from skills.venice_image.image_generation.image_generation_input import STYLE_PRESETS


class ImageGenerationFluxDev(VeniceImageGenerationBaseTool):
    """
    Tool for generating images using Venice AI's Flux Dev model.
    Developed by Black Forest Labs, this is a 12 billion parameter rectified flow transformer.
    """

    # --- Model Specific Configuration ---
    name: str = "image_generation_flux_dev"
    description: str = (
        "Generate images using Venice AI's Flux Dev model (by Black Forest Labs).\n"
        "This 12B parameter model is good for research and innovative art workflows.\n"
        "Provide a text prompt describing the image (up to 2048 chars).\n"
        f"Optionally specify a style preset from the list: {', '.join(STYLE_PRESETS)}.\n"
        "Supports dimensions up to 2048x2048 (multiple of 8).\n"
        "Use complies with FLUX.1 [dev] Non-Commercial License."
    )
    model_id: str = "flux-dev"

    # args_schema and _arun are inherited from VeniceImageGenerationBaseTool
