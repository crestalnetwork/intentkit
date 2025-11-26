"""
S3 utility module for storing and retrieving images from AWS S3.
"""

import logging
from enum import Enum
from io import BytesIO
from typing import cast

import boto3
import filetype
import httpx
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from intentkit.config.config import config

logger = logging.getLogger(__name__)

# Global variables for S3 configuration
_bucket: str | None = None
_client: S3Client | None = None
_prefix: str | None = None
_cdn_url: str | None = None


def get_s3_client() -> S3Client | None:
    """
    Get or initialize S3 client and configuration.
    Returns None if configuration is missing.
    """
    global _bucket, _client, _prefix, _cdn_url

    if _client is not None:
        return _client

    if not config.aws_s3_bucket or not config.aws_s3_cdn_url:
        # Only log once or if needed, but here we just return None
        # The calling functions usually log "S3 not initialized"
        return None

    _bucket = config.aws_s3_bucket
    _cdn_url = config.aws_s3_cdn_url
    _prefix = f"{config.env}/intentkit/"

    try:
        if config.aws_s3_endpoint_url:
            _client = cast(
                S3Client,
                boto3.client(
                    "s3",
                    endpoint_url=config.aws_s3_endpoint_url,
                    region_name=config.aws_s3_region_name,
                    aws_access_key_id=config.aws_s3_access_key_id,
                    aws_secret_access_key=config.aws_s3_secret_access_key,
                ),
            )
            logger.info(
                f"S3 initialized with custom endpoint: {config.aws_s3_endpoint_url}, bucket: {_bucket}, prefix: {_prefix}"
            )
        else:
            _client = cast(S3Client, boto3.client("s3"))
            logger.info(f"S3 initialized with bucket: {_bucket}, prefix: {_prefix}")
        return _client
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return None


async def store_image(url: str, key: str) -> str:
    """
    Store an image from a URL to S3 asynchronously.

    Args:
        url: Source URL of the image
        key: Key to store the image under (without prefix)

    Returns:
        str: The CDN URL of the stored image, or the original URL if S3 is not initialized

    Raises:
        ClientError: If the upload fails
        httpx.HTTPError: If the download fails
    """
    client = get_s3_client()
    if not client or not _bucket or not _prefix or not _cdn_url:
        # If S3 is not initialized, log and return the original URL
        logger.info("S3 not initialized. Returning original URL.")
        return url

    try:
        # Download the image from the URL asynchronously
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url, follow_redirects=True)
            response.raise_for_status()

            # Prepare the S3 key with prefix
            prefixed_key = f"{_prefix}{key}"

            # Use BytesIO to create a file-like object that implements read
            file_obj = BytesIO(response.content)

            # Determine the correct content type
            content_type = response.headers.get("Content-Type", "")
            if content_type == "binary/octet-stream" or not content_type:
                # Try to detect the image type from the content
                kind = filetype.guess(response.content)
                if kind and kind.mime.startswith("image/"):
                    content_type = kind.mime
                else:
                    # Default to JPEG if detection fails
                    content_type = "image/jpeg"

            # Upload to S3
            client.upload_fileobj(
                file_obj,
                _bucket,
                prefixed_key,
                ExtraArgs={"ContentType": content_type, "ContentDisposition": "inline"},
            )

            # Return the CDN URL
            cdn_url = f"{_cdn_url}/{prefixed_key}"
            logger.info(f"Image uploaded successfully to {cdn_url}")
            return cdn_url

    except httpx.HTTPError as e:
        logger.error(f"Failed to download image from URL {url}: {str(e)}")
        raise
    except ClientError as e:
        logger.error(f"Failed to upload image to S3: {str(e)}")
        raise


async def store_image_bytes(
    image_bytes: bytes, key: str, content_type: str | None = None
) -> str:
    """
    Store raw image bytes to S3.

    Args:
        image_bytes: Raw bytes of the image to store
        key: Key to store the image under (without prefix)
        content_type: Content type of the image. If None, will attempt to detect it.

    Returns:
        str: The CDN URL of the stored image, or an empty string if S3 is not initialized

    Raises:
        ClientError: If the upload fails
        ValueError: If S3 is not initialized or image_bytes is empty
    """
    client = get_s3_client()
    if not client or not _bucket or not _prefix or not _cdn_url:
        # If S3 is not initialized, log and return empty string
        logger.info("S3 not initialized. Cannot store image bytes.")
        return ""

    if not image_bytes:
        raise ValueError("Image bytes cannot be empty")

    try:
        # Prepare the S3 key with prefix
        prefixed_key = f"{_prefix}{key}"

        # Use BytesIO to create a file-like object that implements read
        file_obj = BytesIO(image_bytes)

        # Determine the correct content type if not provided
        if not content_type:
            # Try to detect the image type from the content
            kind = filetype.guess(image_bytes)
            if kind and kind.mime.startswith("image/"):
                content_type = kind.mime
            else:
                # Default to JPEG if detection fails
                content_type = "image/jpeg"

        logger.info("uploading image to s3")
        # Upload to S3
        client.upload_fileobj(
            file_obj,
            _bucket,
            prefixed_key,
            ExtraArgs={"ContentType": content_type, "ContentDisposition": "inline"},
        )

        # Return the CDN URL
        cdn_url = f"{_cdn_url}/{prefixed_key}"
        logger.info(f"image is uploaded to {cdn_url}")
        return cdn_url

    except ClientError as e:
        logger.error(f"Failed to upload image bytes to S3: {str(e)}")
        raise


class FileType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    PDF = "pdf"


async def store_file(
    content: bytes,
    key: str,
    content_type: str | None = None,
    size: int | None = None,
) -> str:
    """Store raw file bytes with automatic content type detection."""
    client = get_s3_client()
    if not client or not _bucket or not _prefix or not _cdn_url:
        logger.info("S3 not initialized. Cannot store file bytes.")
        return ""

    if not content:
        raise ValueError("File content cannot be empty")

    actual_size = len(content)
    if size is not None and size != actual_size:
        raise ValueError(
            f"Provided size {size} does not match actual content size {actual_size} bytes"
        )

    effective_size = size if size is not None else actual_size

    detected_content_type = content_type
    if not detected_content_type:
        kind = filetype.guess(content)
        detected_content_type = (
            kind.mime if kind and kind.mime else "application/octet-stream"
        )

    prefixed_key = f"{_prefix}{key}"
    file_obj = BytesIO(content)

    logger.info(
        "Uploading file to S3 with content type %s and size %s bytes",
        detected_content_type,
        effective_size,
    )

    client.upload_fileobj(
        file_obj,
        _bucket,
        prefixed_key,
        ExtraArgs={
            "ContentType": detected_content_type,
            "ContentDisposition": "inline",
        },
    )

    cdn_url = f"{_cdn_url}/{prefixed_key}"
    logger.info("File uploaded successfully to %s", cdn_url)
    return cdn_url


async def store_file_bytes(
    file_bytes: bytes,
    key: str,
    file_type: FileType,
    size_limit_bytes: int | None = None,
) -> str:
    """
    Store raw file bytes (image, video, sound, pdf) to S3.

    Args:
        file_bytes: Raw bytes of the file to store
        key: Key to store the file under (without prefix)
        file_type: Type of the file (image, video, sound, pdf)
        size_limit_bytes: Optional size limit in bytes

    Returns:
        str: The CDN URL of the stored file, or an empty string if S3 is not initialized

    Raises:
        ClientError: If the upload fails
        ValueError: If S3 is not initialized, file_bytes is empty, or file exceeds size limit
    """
    client = get_s3_client()
    if not client or not _bucket or not _prefix or not _cdn_url:
        logger.info("S3 not initialized. Cannot store file bytes.")
        return ""
    if not file_bytes:
        raise ValueError("File bytes cannot be empty")

    if size_limit_bytes is not None and len(file_bytes) > size_limit_bytes:
        raise ValueError(
            f"File size exceeds the allowed limit of {size_limit_bytes} bytes"
        )

    try:
        # Prepare the S3 key with prefix
        prefixed_key = f"{_prefix}{key}"

        # Use BytesIO to create a file-like object that implements read
        file_obj = BytesIO(file_bytes)

        # Determine content type based on file_type
        content_type = ""
        if file_type == FileType.IMAGE:
            kind = filetype.guess(file_bytes)
            if kind and kind.mime.startswith("image/"):
                content_type = kind.mime
            else:
                content_type = "image/jpeg"
        elif file_type == FileType.VIDEO:
            kind = filetype.guess(file_bytes)
            if kind and kind.mime.startswith("video/"):
                content_type = kind.mime
            else:
                content_type = "video/mp4"
        elif file_type == FileType.AUDIO:
            kind = filetype.guess(file_bytes)
            if kind and kind.mime.startswith("audio/"):
                content_type = kind.mime
            else:
                content_type = "audio/mpeg"
        elif file_type == FileType.PDF:
            content_type = "application/pdf"
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        logger.info(f"Uploading {file_type} to S3 with content type {content_type}")

        # Upload to S3
        client.upload_fileobj(
            file_obj,
            _bucket,
            prefixed_key,
            ExtraArgs={"ContentType": content_type, "ContentDisposition": "inline"},
        )

        # Return the CDN URL
        cdn_url = f"{_cdn_url}/{prefixed_key}"
        logger.info(f"{file_type} uploaded successfully to {cdn_url}")
        return cdn_url

    except ClientError as e:
        logger.error(f"Failed to upload {file_type} bytes to S3: {str(e)}")
        raise
