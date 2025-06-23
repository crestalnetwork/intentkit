from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

STYLE_PRESETS = [
    "3D Model",
    "Analog Film",
    "Anime",
    "Cinematic",
    "Comic Book",
    "Craft Clay",
    "Digital Art",
    "Enhance",
    "Fantasy Art",
    "Isometric Style",
    "Line Art",
    "Lowpoly",
    "Neon Punk",
    "Origami",
    "Photographic",
    "Pixel Art",
    "Texture",
    "Advertising",
    "Food Photography",
    "Real Estate",
    "Abstract",
    "Cubist",
    "Graffiti",
    "Hyperrealism",
    "Impressionist",
    "Pointillism",
    "Pop Art",
    "Psychedelic",
    "Renaissance",
    "Steampunk",
    "Surrealist",
    "Typography",
    "Watercolor",
    "Fighting Game",
    "GTA",
    "Super Mario",
    "Minecraft",
    "Pokemon",
    "Retro Arcade",
    "Retro Game",
    "RPG Fantasy Game",
    "Strategy Game",
    "Street Fighter",
    "Legend of Zelda",
    "Architectural",
    "Disco",
    "Dreamscape",
    "Dystopian",
    "Fairy Tale",
    "Gothic",
    "Grunge",
    "Horror",
    "Minimalist",
    "Monochrome",
    "Nautical",
    "Space",
    "Stained Glass",
    "Techwear Fashion",
    "Tribal",
    "Zentangle",
    "Collage",
    "Flat Papercut",
    "Kirigami",
    "Paper Mache",
    "Paper Quilling",
    "Papercut Collage",
    "Papercut Shadow Box",
    "Stacked Papercut",
    "Thick Layered Papercut",
    "Alien",
    "Film Noir",
    "HDR",
    "Long Exposure",
    "Neon Noir",
    "Silhouette",
    "Tilt-Shift",
]

STYLE_PRESETS_DESCRIPTION = (
    "Optional style preset to apply. Available options: "
    + ", ".join([f"'{s}'" for s in STYLE_PRESETS])
    + ". Defaults to 'Photographic'."
)


class InpaintMask(BaseModel):
    image_prompt: str = Field(
        ...,
        description="A text prompt describing the original input image that an image model would use to produce a similar/identical image, including the changed features the user will be inpainting.",
    )
    inferred_object: str = Field(
        ..., description="The content being added via inpainting."
    )
    object_target: str = Field(
        ..., description="Element(s) in the original image to be inpainted over."
    )


class Inpaint(BaseModel):
    image_url: HttpUrl = Field(
        ...,
        description="Image target to inpaint",
    )
    strength: int = Field(
        ..., ge=0, le=100, description="Strength of the inpainting (0-100).", example=50
    )
    mask: InpaintMask = Field(..., description="Mask settings for inpainting.")


class VeniceImageGenerationInput(BaseModel):
    """Model representing input parameters for Venice Image Generation."""

    prompt: str = Field(
        description="The main text prompt describing what should be included in the generated image."
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed value to control image generation randomness. "
        "Use the same seed to reproduce identical results. If not set, a random seed will be used.",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="Text describing what should be excluded from the generated image. "
        "If not provided, the default agent configuration will be used.",
    )
    width: Optional[int] = Field(
        default=1024,
        le=2048,
        description="Width of the generated image in pixels. Maximum allowed is 2048. Default is 1024.",
    )
    height: Optional[int] = Field(
        default=1024,
        le=2048,
        description="Height of the generated image in pixels. Maximum allowed is 2048. Default is 1024.",
    )
    format: Literal["png", "jpeg", "webp"] = Field(
        default="png",
        description="Output image format. Options are 'png', 'jpeg', or 'webp'. Defaults to 'png'.",
    )
    cfg_scale: Optional[float] = Field(
        default=7.5,
        description="Classifier-Free Guidance (CFG) scale controls how closely the image follows the prompt. "
        "Higher values (1-20) result in more adherence. Default is 7.5.",
    )
    style_preset: Optional[str] = Field(
        default="Photographic", description=STYLE_PRESETS_DESCRIPTION
    )
    inpainting: Optional[Inpaint] = Field(
        default=None,
        description="Optional inpainting operation that allows modification of specific objects within an image. "
        "Requires an original image url, a strength value (0-100), and detailed mask instructions "
        "to define which part of the image should be edited and what should replace it.",
    )
