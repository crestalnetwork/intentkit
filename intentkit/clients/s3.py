"""
S3 utility module for storing and retrieving images from AWS S3.
"""

import ipaddress
import logging
from enum import Enum
from io import BytesIO
from typing import cast
from urllib.parse import urlparse

import boto3
import filetype
import httpx
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
    _prefix = f"{config.env}/"

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
            logger.info("S3 initialized with bucket: %s, prefix: %s", _bucket, _prefix)
        return _client
    except Exception as e:
        logger.error("Failed to initialize S3 client: %s", e)
        return None


def get_cdn_url(relative_path: str) -> str:
    """
    Build a full CDN URL from a relative path.

    This should be used by tools when they need to return an accessible URL
    to the agent. The database should always store relative paths.

    Args:
        relative_path: The relative path (e.g. "env/agent_id/image.png")

    Returns:
        str: The full CDN URL (e.g. "https://cdn.example.com/env/agent_id/image.png")
    """
    cdn_base = _cdn_url or config.aws_s3_cdn_url
    if not cdn_base:
        return relative_path
    return f"{cdn_base}/{relative_path}"


_MIME_EXTENSION_OVERRIDES = {
    "image/jpeg": "jpg",
}


def _extension_for_mime(mime: str) -> str:
    """Return a sensible file extension for an image MIME type."""
    import mimetypes

    if mime in _MIME_EXTENSION_OVERRIDES:
        return _MIME_EXTENSION_OVERRIDES[mime]
    ext = mimetypes.guess_extension(mime)
    return ext.lstrip(".") if ext else "bin"


def _check_url_safety(url: str) -> None:
    """Reject URLs that target internal/private network addresses.

    Defends against direct SSRF (LLM-supplied URL pointing at internal
    services like cloud metadata endpoints or docker service names). Does
    NOT defend against DNS rebinding — a public hostname that resolves to a
    private IP at request time. Closing that hole would require a custom
    httpx Transport that re-validates the resolved IP before connecting.

    Raises:
        ValueError: If the URL targets a blocked address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Only http(s) URLs are supported, got scheme: {parsed.scheme!r}"
        )
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Invalid URL (no hostname): {url}")
    # Strip trailing dot (FQDN notation) so "localhost." cannot bypass the check.
    hostname = hostname.rstrip(".")
    if "." not in hostname:
        raise ValueError(
            f"Blocked single-segment hostname {hostname!r} "
            "(likely an internal service name)"
        )
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # Not an IP literal — a domain name, which is fine
        return
    if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local:
        raise ValueError(f"Blocked internal/reserved IP: {hostname}")


_REDIRECT_STATUSES = (301, 302, 303, 307, 308)
_MAX_REDIRECTS = 3
_ERROR_BODY_PREVIEW_CAP = 1024  # cap bytes read from a non-200 body


async def download_image_bytes(
    url: str, max_bytes: int = 20 * 1024 * 1024
) -> tuple[bytes, str, str]:
    """Stream-download an image URL into memory with SSRF protection.

    Validates each URL in the redirect chain against private/reserved
    address ranges, manually follows up to ``_MAX_REDIRECTS`` hops, and
    enforces ``max_bytes`` on both the success body and the bounded preview
    of any error body. Image identity is checked strictly via magic-byte
    sniffing — the server's Content-Type header is not trusted (an
    attacker-served ``image/svg+xml`` with ``<script>`` would otherwise
    become stored XSS on our CDN, which serves uploads with
    ``ContentDisposition: inline``).

    Args:
        url: Source URL to download.
        max_bytes: Hard cap on the downloaded size; default 20 MiB.

    Returns:
        Tuple of (raw bytes, detected ``image/*`` content type, extension).

    Raises:
        httpx.HTTPError: Network failure, or a 4xx/5xx response (message
            includes a bounded preview of the response body).
        ValueError: If the URL targets an internal address, redirects too
            many times, exceeds ``max_bytes``, or is not an image.
    """
    content = b""
    async with httpx.AsyncClient(timeout=30) as http_client:
        current_url = url
        redirects = 0
        while True:
            # Validate every URL in the chain — a public host can otherwise
            # redirect to 169.254.169.254 (cloud metadata) etc.
            _check_url_safety(current_url)

            async with http_client.stream(
                "GET", current_url, follow_redirects=False
            ) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    if redirects >= _MAX_REDIRECTS:
                        raise ValueError(f"Too many redirects (>{_MAX_REDIRECTS})")
                    location = response.headers.get("location")
                    if not location:
                        raise httpx.HTTPStatusError(
                            f"Redirect {response.status_code} missing Location header",
                            request=response.request,
                            response=response,
                        )
                    current_url = str(httpx.URL(current_url).join(location))
                    redirects += 1
                    continue

                if response.status_code >= 400:
                    # Cap the error-body read so a malicious server can't OOM
                    # us by attaching a huge body to a 4xx/5xx response.
                    body_buf = bytearray()
                    async for chunk in response.aiter_bytes():
                        body_buf.extend(chunk)
                        if len(body_buf) >= _ERROR_BODY_PREVIEW_CAP:
                            break
                    body_preview = (
                        bytes(body_buf)[:200].decode("utf-8", errors="replace").strip()
                    )
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code} for {current_url}: {body_preview}",
                        request=response.request,
                        response=response,
                    )

                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        declared = int(content_length)
                    except ValueError:
                        declared = None
                    if declared is not None and declared > max_bytes:
                        raise ValueError(
                            f"Response too large: {declared} bytes (limit: {max_bytes})"
                        )
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"Response too large: >{max_bytes} bytes")
                    chunks.append(chunk)
                content = b"".join(chunks)
                break

    # Strict magic-byte sniffing only. We deliberately do not fall back to
    # the server-declared Content-Type (see docstring for the XSS-via-SVG
    # rationale). filetype only inspects the head — slice to keep it cheap.
    kind = filetype.guess(content[:512])
    if not kind or not kind.mime.startswith("image/"):
        detected = kind.mime if kind else "unknown"
        raise ValueError(f"URL does not point to an image (detected: {detected})")

    ext = kind.extension or _extension_for_mime(kind.mime)
    return content, kind.mime, ext


async def store_image(url: str, key: str) -> str:
    """
    Store an image from a URL to S3 asynchronously.

    Args:
        url: Source URL of the image
        key: Key to store the image under (without prefix)

    Returns:
        str: The relative path of the stored image, or the original URL if S3 is not initialized

    Raises:
        ClientError: If the upload fails
        httpx.HTTPError: If the download fails
    """
    client = get_s3_client()
    if not client or not _bucket or not _prefix or not _cdn_url:
        # If S3 is not initialized, log and return the original URL
        logger.info("S3 not initialized. Returning original URL.")
        return url

    max_content_length = 20 * 1024 * 1024  # 20 MB

    # Download the image from the URL asynchronously using streaming
    # to avoid buffering oversized responses into memory.
    async with httpx.AsyncClient(timeout=30) as http_client:
        async with http_client.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_content_length:
                raise ValueError(
                    f"Response too large: {content_length} bytes (limit: {max_content_length})"
                )
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_content_length:
                    raise ValueError(f"Response too large: >{max_content_length} bytes")
                chunks.append(chunk)
        content = b"".join(chunks)
        resp_content_type = response.headers.get("Content-Type", "")

    # Prepare the S3 key with prefix
    prefixed_key = f"{_prefix}{key}"

    # Use BytesIO to create a file-like object that implements read
    file_obj = BytesIO(content)

    # Determine the correct content type
    content_type = resp_content_type
    if content_type == "binary/octet-stream" or not content_type:
        # Try to detect the image type from the content
        kind = filetype.guess(content)
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

    # Return the relative path
    logger.info("Image uploaded successfully to %s", prefixed_key)
    return prefixed_key


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
        str: The relative path of the stored image, or an empty string if S3 is not initialized

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

    # Return the relative path
    logger.info("image is uploaded to %s", prefixed_key)
    return prefixed_key


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

    # Return the relative path
    logger.info("File uploaded successfully to %s", prefixed_key)
    return prefixed_key


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
        str: The relative path of the stored file, or an empty string if S3 is not initialized

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
        raise ValueError(f"Unsupported file type: {file_type}")  # pyright: ignore[reportUnreachable]

    logger.info("Uploading %s to S3 with content type %s", file_type, content_type)

    # Upload to S3
    client.upload_fileobj(
        file_obj,
        _bucket,
        prefixed_key,
        ExtraArgs={"ContentType": content_type, "ContentDisposition": "inline"},
    )

    # Return the relative path
    logger.info("%s uploaded successfully to %s", file_type, prefixed_key)
    return prefixed_key
