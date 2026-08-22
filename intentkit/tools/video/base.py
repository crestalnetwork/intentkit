"""Base class for video generation tools.

Every video model is served through OpenRouter's video generation API
(``POST /videos`` -> poll ``GET /videos/{jobId}`` -> ``GET
/videos/{jobId}/content``), so this base carries the whole flow and
subclasses only name a model.

Billing is metered rather than flat: providers charge on the actual output
(model, resolution, duration) and OpenRouter reports that figure as
``usage.cost``, which the tool reports in USD via
``tools.base.report_tool_cost_usd``. ``price`` remains as the fallback for a
job that finishes without a usage figure.
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Annotated, Any, Literal, override

import httpx
import openrouter
from epyxid import XID
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langchain_core.tools.base import ToolException
from openrouter.components import VideoGenerationResponse
from pydantic import BaseModel, Field

from intentkit.clients.openrouter import bounded_retry_config, get_openrouter_client
from intentkit.clients.s3 import FileType, get_cdn_url, store_file_bytes
from intentkit.config.config import config
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType
from intentkit.tools.base import IntentKitTool, report_tool_cost_usd
from intentkit.utils.media import to_data_url
from intentkit.utils.ssrf import httpx_request_guard

logger = logging.getLogger(__name__)

# Polling schedule. Jobs run from seconds to minutes, so back off from a quick
# first check rather than paying a flat interval for every status poll.
FIRST_POLL_DELAY = 2  # seconds before the first status check
MAX_POLL_INTERVAL = 10  # ceiling for the backoff between checks
MAX_POLL_TIME = 300  # 5 minutes max wait
# Consecutive status-request failures tolerated before giving up on a job.
MAX_POLL_ERRORS = 3
POLL_TIMEOUT_MS = 30_000  # per status request; the client default sizes the download
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB


def usage_cost_usd(job: VideoGenerationResponse) -> Decimal | None:
    """Extract the job's USD cost, or None when the API did not report one.

    The SDK models ``usage.cost`` as ``OptionalNullable[float]``: an omitted
    field is its ``Unset()`` sentinel, not ``None``. That sentinel is truthy
    for an ``is not None`` test and ``str()``s to the empty string, so feeding
    it to ``Decimal`` raises — which would have thrown away a video the
    provider had already generated and charged for. Accept only real numbers.
    """
    cost = getattr(job.usage, "cost", None) if job.usage else None
    if not isinstance(cost, (int, float)) or isinstance(cost, bool):
        return None
    return Decimal(str(cost))


class VideoGenerationInput(BaseModel):
    """Input for video generation tools."""

    prompt: str = Field(description="Video description prompt")
    image: str | None = Field(
        default=None,
        description="Optional input image URL, used as the first frame for "
        "image-to-video generation",
    )


class VideoBaseTool(IntentKitTool):
    """Base class for all video generation tools.

    Submits the job to OpenRouter, polls it to completion, stores the result
    on S3 and returns it as an attachment.
    """

    category: str = "video"
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    args_schema: ArgsSchema | None = VideoGenerationInput

    # Subclasses set this to an OpenRouter video model id.
    openrouter_model: str = ""

    @override
    def available(self) -> bool:
        """Video generation needs an OpenRouter key and a model to route to."""
        return bool(config.openrouter_api_key) and bool(self.openrouter_model)

    def _client(self) -> openrouter.OpenRouter:
        try:
            # One job makes up to ~60 HTTP calls, so the SDK's hour-long
            # default retry budget has to be bounded well inside MAX_POLL_TIME.
            return get_openrouter_client(retry_config=bounded_retry_config())
        except ValueError as e:
            raise ToolException(str(e))

    async def _download_image(self, url: str) -> bytes:
        """Download the first-frame image. The URL is a tool argument, so the
        client carries the SSRF guard."""
        async with httpx.AsyncClient(
            timeout=30, event_hooks={"request": [httpx_request_guard]}
        ) as client:
            resp = await client.get(url, follow_redirects=True)
            _ = resp.raise_for_status()
            return resp.content

    def _frame_images(self, image: bytes | None) -> list[dict[str, Any]] | None:
        """Build the first-frame reference for image-to-video."""
        if not image:
            return None
        return [
            {
                "type": "image_url",
                "frame_type": "first_frame",
                "image_url": {"url": to_data_url(image)},
            }
        ]

    async def _generate(
        self, prompt: str, image: bytes | None
    ) -> tuple[bytes, Decimal | None]:
        """Run one generation job. Returns the mp4 bytes and its USD cost."""
        frame_images = self._frame_images(image)

        # The SDK builds an httpx client pair per instance; close them with the
        # job rather than leaving two pools per generation to the collector.
        async with self._client() as client:
            try:
                job = await client.video_generation.generate_async(
                    model=self.openrouter_model,
                    prompt=prompt,
                    frame_images=frame_images,  # pyright: ignore[reportArgumentType]
                )
            except Exception as e:
                raise ToolException(f"OpenRouter video request failed: {e}")

            job_id = job.id
            if not job_id:
                raise ToolException("No job id in OpenRouter video response")

            job = await self._poll(client, job_id)
            video_bytes = await self._download_video(client, job_id)

        return video_bytes, usage_cost_usd(job)

    async def _download_video(
        self, client: openrouter.OpenRouter, job_id: str
    ) -> bytes:
        """Fetch the finished video, refusing an oversized body up front.

        The SDK hands back an unread streaming response, so the size check has
        to happen before the body is buffered — otherwise a 500 MB response is
        fully materialized only to be rejected — and the response has to be
        closed to release the connection.
        """
        try:
            response = await client.video_generation.get_video_content_async(
                job_id=job_id
            )
        except Exception as e:
            raise ToolException(f"Failed to download generated video: {e}")

        try:
            _ = response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and int(declared) > MAX_VIDEO_SIZE:
                raise ToolException(f"Video too large: {declared} bytes")

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                # Servers may omit or understate content-length; stop reading
                # as soon as the real body crosses the limit.
                if total > MAX_VIDEO_SIZE:
                    raise ToolException(f"Video too large: over {MAX_VIDEO_SIZE} bytes")
                chunks.append(chunk)
            return b"".join(chunks)
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to read generated video: {e}")
        finally:
            await response.aclose()

    async def _poll(
        self, client: openrouter.OpenRouter, job_id: str
    ) -> VideoGenerationResponse:
        """Poll a submitted job until it completes, fails, or times out.

        The deadline is wall-clock: counting only the sleeps would let request
        latency and the SDK's own retries run well past MAX_POLL_TIME.

        A failing status request is not a failing job. The provider bills for
        the generation either way, and a ToolException here is terminal
        (_should_retry_tool_failure never retries one), so giving up on the
        first flaky poll would drop a video we have already paid for. Keep
        polling until the run of errors looks like a real outage, or the
        deadline passes.
        """
        deadline = time.monotonic() + MAX_POLL_TIME
        delay = FIRST_POLL_DELAY
        consecutive_errors = 0

        while True:
            # Checked before sleeping, so an expired budget isn't spent on one
            # more wait and one more request.
            if time.monotonic() >= deadline:
                raise ToolException(
                    f"Video generation timed out after {MAX_POLL_TIME} seconds"
                )

            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_POLL_INTERVAL)

            try:
                job = await client.video_generation.get_generation_async(
                    job_id=job_id,
                    # A status check is a small GET; the client-wide timeout is
                    # sized for the video download, and one hung poll must not
                    # eat two minutes of the budget.
                    timeout_ms=POLL_TIMEOUT_MS,
                )
            except Exception as e:
                consecutive_errors += 1
                if (
                    consecutive_errors >= MAX_POLL_ERRORS
                    or time.monotonic() >= deadline
                ):
                    raise ToolException(f"Failed to poll video generation: {e}")
                self.logger.warning(
                    "[%s] poll %s failed (%s/%s), retrying: %s",
                    self.name,
                    job_id,
                    consecutive_errors,
                    MAX_POLL_ERRORS,
                    e,
                )
                continue
            consecutive_errors = 0

            status = str(job.status)
            if status == "completed":
                return job
            if status in ("failed", "cancelled", "expired"):
                # job.error is UNSET when absent, which is falsy — the fallback
                # below covers both that and None.
                raise ToolException(
                    f"Video generation {status}: {job.error or 'no detail given'}"
                )

    async def _upload_and_return(
        self, video_bytes: bytes, context: Any, tool_name: str
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Upload video to S3 and return text + attachment tuple."""
        job_id = str(XID())
        video_key = f"{context.agent_id}/video/{tool_name}/{job_id}.mp4"
        stored_path = await store_file_bytes(video_bytes, video_key, FileType.VIDEO)
        if not stored_path:
            raise ToolException("Failed to store video: S3 storage not configured")
        url = get_cdn_url(stored_path)

        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.VIDEO,
            "lead_text": None,
            "url": url,
            "json": None,
        }
        return (
            f"Video generated successfully: {url} . "
            "The video has been displayed to the user via attachment. "
            "Do not include the video URL in your response unless the user explicitly asks for it."
        ), [attachment]

    @override
    async def _arun(
        self,
        prompt: str,
        image: str | None = None,
        tool_call_id: Annotated[str | None, InjectedToolCallId] = None,
        **kwargs: Any,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Orchestrate video generation: generate -> meter -> upload -> return."""
        context = self.get_context()

        try:
            input_image: bytes | None = None
            if image:
                input_image = await self._download_image(image)

            video_bytes, usd = await self._generate(prompt, input_image)
            if usd is None:
                self.logger.warning(
                    "[%s] job reported no usage cost; billing at the flat price",
                    self.name,
                )
            else:
                report_tool_cost_usd(tool_call_id, usd)

            return await self._upload_and_return(video_bytes, context, self.name)

        except ToolException:
            raise
        except httpx.HTTPStatusError as e:
            raise ToolException(
                f"API request failed: {e.response.status_code} {e.response.text[:200]}"
            )
        except Exception as e:
            raise ToolException(f"Error generating video with {self.name}: {e}")
