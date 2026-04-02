"""Shared image upload utilities."""

from epyxid import XID
from fastapi import UploadFile

from intentkit.clients.s3 import store_image_bytes
from intentkit.utils.error import IntentKitAPIError

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


async def validate_and_store_image(file: UploadFile, key_prefix: str) -> str:
    """Validate an uploaded image and store it in S3.

    Args:
        file: The uploaded file.
        key_prefix: S3 key prefix (e.g. "avatars/user/", "avatars/").

    Returns:
        The S3 path of the stored image.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise IntentKitAPIError(400, "BadRequest", "File must be an image")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise IntentKitAPIError(400, "BadRequest", "Image must be less than 5MB")

    ext = (
        file.filename.rsplit(".", 1)[-1].lower()
        if file.filename and "." in file.filename
        else ""
    )
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = "jpg"
    key = f"{key_prefix}{XID()}.{ext}"

    path = await store_image_bytes(content, key, content_type=file.content_type)
    if not path:
        raise IntentKitAPIError(500, "ServerError", "Failed to upload image to storage")

    return path
