"""Tool for persisting an external image URL to our S3-backed CDN."""

import logging
from typing import Annotated, override

import httpx
from epyxid import XID
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients.s3 import (
    download_image_bytes,
    get_cdn_url,
    store_image_bytes,
)
from intentkit.config.config import config
from intentkit.core.system_tools.base import SystemTool

logger = logging.getLogger(__name__)


class StoreImageInput(BaseModel):
    """Input schema for storing an external image."""

    url: str = Field(
        ...,
        description="HTTP(S) URL of a publicly accessible image to persist.",
    )


class StoreImageTool(SystemTool):
    """Download an image from a public URL and store it on our CDN.

    Returns the persistent CDN URL of the stored image, suitable for
    embedding in markdown as ``![](url)``. Useful when the agent wants to
    include an external image (e.g. one discovered via web search) in
    long-form output and needs the link to keep working after the source
    site changes.
    """

    name: str = "store_image"
    description: str = (
        "Download an image from a public URL and store it on our CDN. "
        "Returns the persistent CDN URL of the stored image. Use this when "
        "you need to embed an external image in markdown output (e.g. in an "
        "article you are writing) so the link stays valid after the source "
        "site changes. Input is a single image URL; output is one CDN URL. "
        "Images already on our CDN (e.g. ones you just generated) are "
        "persistent — do not call this on them."
    )
    args_schema: ArgsSchema | None = StoreImageInput

    @override
    async def _arun(
        self,
        url: str,
        tool_call_id: Annotated[str | None, InjectedToolCallId] = None,
    ) -> str:
        """Download ``url``, validate as image, upload to S3, return CDN URL."""
        try:
            # URLs already on our CDN are persistent by definition; re-storing
            # them would only duplicate the object. Match on prefix + "/" so a
            # lookalike host (cdn.example.com.evil.com) doesn't short-circuit.
            cdn_base = (config.aws_s3_cdn_url or "").rstrip("/")
            if cdn_base and url.startswith(f"{cdn_base}/"):
                return url

            context = self.get_context()

            try:
                content, content_type, ext = await download_image_bytes(url)
            except ValueError as e:
                raise ToolException(str(e)) from e
            except httpx.HTTPError as e:
                raise ToolException(f"Failed to download image: {e}") from e

            key = f"{context.agent_id}/image/store_image/{XID()}.{ext}"

            relative_path = await store_image_bytes(
                content, key, content_type=content_type
            )
            if not relative_path:
                raise ToolException("S3 storage is not configured")

            return get_cdn_url(relative_path)

        except ToolException:
            raise
        except Exception as e:
            logger.exception("store_image failed: %s", e)
            raise ToolException(f"Failed to store image: {e}") from e
