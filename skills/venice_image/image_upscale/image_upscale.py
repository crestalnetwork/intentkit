from skills.venice_image.image_upscale.image_upscale_base import (
    VeniceImageUpscaleBaseTool,
)


class ImageUpscale(VeniceImageUpscaleBaseTool):
    """
    Upscales an existing image provided via URL by a factor of 2 or 4 using the Venice AI API.
    Ideal for enhancing the resolution of previously generated or existing images.
    """

    # --- Tool Specific Configuration ---
    name: str = "image_upscale"
    description: str = (
        "Upscales an existing image from a URL using Venice AI.\n"
        "Provide the public URL of the image to upscale.\n"
        "Specify the desired scale factor: 2 (for 2x upscale) or 4 (for 4x upscale).\n"
        "Returns the URL of the upscaled image."
    )
    # No model_id needed for the generic upscale endpoint currently

    # args_schema and _arun are inherited from VeniceImageUpscaleBaseTool
