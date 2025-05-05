# venice_image/image_generation_flux_dev_uncensored.py
from skills.venice_image.base import VeniceImageBaseTool
from skills.venice_image.input import STYLE_PRESETS  # Keep for description


class ImageGenerationFluxDevUncensored(VeniceImageBaseTool):
    """
    Tool for generating images using Venice AI's Flux Dev Uncensored model.
    An uncensored version of the flux-dev model for unrestricted generation.
    """

    # --- Model Specific Configuration ---
    name: str = "venice_image_generation_flux_dev_uncensored"
    description: str = (
        "Generate images using Venice AI's Flux Dev Uncensored model.\n"
        "This is an uncensored version of flux-dev, suitable for unrestricted content including NSFW.\n"
        "Provide a text prompt describing the image (up to 2048 chars).\n"
        f"Optionally specify a style preset from the list: {', '.join(STYLE_PRESETS)}.\n"
        "Supports dimensions up to 2048x2048 (multiple of 8)."
    )
    model_id: str = "flux-dev-uncensored"

    # args_schema and _arun are inherited from VeniceImageBaseTool
