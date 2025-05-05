from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class VeniceImageRequestData(BaseModel):
    cfg_scale: float = Field(
        ..., description="Classifier-Free Guidance scale value for generation."
    )
    embed_exif_metadata: bool = Field(
        ..., description="Whether to embed EXIF metadata into the image."
    )
    format: Literal["png", "jpeg", "webp"] = Field(
        ..., description="The desired output format of the image."
    )
    height: int = Field(..., description="The height of the generated image in pixels.")
    hide_watermark: bool = Field(
        ..., description="Whether to hide the default watermark."
    )
    model: str = Field(
        ..., description="The name or ID of the model used to generate the image."
    )
    negative_prompt: Optional[str] = Field(
        None, description="Optional prompt to avoid specific features in the image."
    )
    prompt: str = Field(
        ..., description="The main text prompt used to generate the image."
    )
    return_binary: bool = Field(
        ..., description="Whether the image should be returned in binary format."
    )
    safe_mode: bool = Field(
        ..., description="If true, the image generation is subject to safety filters."
    )
    seed: int = Field(
        ...,
        description="Random seed used for image generation. Same seed gives repeatable results.",
    )
    steps: int = Field(..., description="Number of inference steps to run.")
    style_preset: str = Field(
        ..., description="The style preset used to stylize the generated image."
    )
    width: int = Field(..., description="The width of the generated image in pixels.")


class VeniceImageRequest(BaseModel):
    success: bool = Field(
        ..., description="Indicates whether the generation request was successful."
    )
    data: VeniceImageRequestData = Field(
        ..., description="Detailed parameters used during image generation."
    )


class VeniceImageGenerationResponse(BaseModel):
    id: str = Field(
        ..., description="Unique identifier for this image generation request."
    )
    images: List[str] = Field(
        ..., description="List of base64-encoded image strings (usually one)."
    )
    request: VeniceImageRequest = Field(
        ..., description="Request metadata and generation parameters."
    )
