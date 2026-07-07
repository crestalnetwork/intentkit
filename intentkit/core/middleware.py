from __future__ import annotations

import logging
import mimetypes
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, override

from langchain.agents.middleware import AgentMiddleware, LLMToolSelectorMiddleware
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest, ModelResponse

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.prompt import build_system_prompt
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import AuthorType
from intentkit.models.llm import LLMModel

logger = logging.getLogger(__name__)


class DynamicPromptMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that builds the system prompt dynamically per request."""

    agent: Agent
    agent_data: AgentData

    def __init__(self, agent: Agent, agent_data: AgentData) -> None:
        super().__init__()
        self.agent = agent
        self.agent_data = agent_data

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context: AgentContext = request.runtime.context
        system_prompt = await build_system_prompt(self.agent, self.agent_data, context)
        updated_request = request.override(system_prompt=system_prompt)  # pyright: ignore[reportCallIssue]
        return await handler(updated_request)


class ToolBindingMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that selects tools and model parameters based on context."""

    llm_model: LLMModel
    # Named all_tools: AgentMiddleware.tools has different semantics (tools a
    # middleware itself contributes to the graph).
    all_tools: list[BaseTool | dict[str, Any]]
    extra_llm_params: dict[str, Any]

    def __init__(
        self,
        llm_model: LLMModel,
        all_tools: list[BaseTool | dict[str, Any]],
        extra_llm_params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.llm_model = llm_model
        self.all_tools = all_tools
        self.extra_llm_params = extra_llm_params or {}

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        context: AgentContext = request.runtime.context

        llm_params: dict[str, Any] = {**self.extra_llm_params}
        # Tools are deduplicated at build time in executor.py. Tools marked
        # team_only (publishing, signing, spending) are hidden from guests of
        # a published agent; each such tool re-checks at execution time too.
        # Tools marked interactive_only (UI cards, choice buttons) need a live
        # user watching the conversation, so they are hidden from cron-
        # triggered runs and sub-agent calls.
        # getattr covers dict-typed provider server tools too (no flag).
        interactive_allowed = (
            context.entrypoint != AuthorType.TRIGGER and not context.is_subagent
        )
        tools: list[BaseTool | dict[str, Any]] = [
            t
            for t in self.all_tools
            if (context.is_own_team or not getattr(t, "team_only", False))
            and (interactive_allowed or not getattr(t, "interactive_only", False))
        ]

        model = await self.llm_model.create_instance(llm_params)
        updated_request = request.override(
            model=model,
            tools=tools,
            model_settings=llm_params,
        )
        return await handler(updated_request)


class StepTrackingMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware that tracks the number of steps in the agent execution."""

    @override
    async def abefore_model(
        self, state: AgentState, runtime: Runtime[AgentContext]
    ) -> dict[str, Any]:
        del runtime
        step_count = state.get("step_count", 0)
        step_count += 1
        logger.debug("Step tracking: %s", step_count)
        return {"step_count": step_count}


class EmptyContentSafetyMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Sanitize AIMessages with empty list content to prevent Gemini 3 API errors.

    Gemini 3 stores empty content as [] (list) instead of "" (string).
    If tool_calls are lost from such a message (e.g. during checkpoint
    serialization), converting content=[] produces Content(parts=[]) which
    the Gemini API rejects with "must include at least one parts field".

    This middleware patches any such message before the model call.
    """

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        messages = request.messages
        patched = False
        for i, msg in enumerate(messages):
            if (
                isinstance(msg, AIMessage)
                and isinstance(msg.content, list)
                and len(msg.content) == 0
                and not msg.tool_calls
            ):
                messages[i] = msg.model_copy(update={"content": ""})
                patched = True
                logger.warning(
                    "Patched AIMessage with empty content[] at index %d "
                    "(no tool_calls) — would have caused Gemini empty-parts error",
                    i,
                )
        if patched:
            request = request.override(messages=messages)
        return await handler(request)


_MEDIA_BLOCK_TYPES = frozenset({"image", "audio", "video", "file"})
_MEDIA_DEFAULT_MIME: dict[str, str] = {
    "image": "image/jpeg",
    "audio": "audio/mpeg",
    "video": "video/mp4",
    "file": "application/octet-stream",
}


def _as_media_block(block: Any) -> dict[str, Any] | None:
    if not isinstance(block, dict):
        return None
    if block.get("type") not in _MEDIA_BLOCK_TYPES:
        return None
    if not (block.get("url") or block.get("base64") or block.get("data")):
        return None
    return block


def _resolve_mime_type(block: dict[str, Any]) -> str | None:
    btype = block.get("type")
    url = block.get("url")
    guessed: str | None = None
    if isinstance(url, str) and url:
        path_only = url.split("?", 1)[0].split("#", 1)[0]
        guessed, _ = mimetypes.guess_type(path_only)
    if btype == "file":
        # Downstream model APIs (e.g. Gemini) reject application/octet-stream
        # outright, so a `.bin` extension or a per-type default doesn't help.
        # Only return a guess we'd actually consider sendable.
        if guessed and guessed != "application/octet-stream":
            return guessed
        return None
    if guessed:
        return guessed
    return _MEDIA_DEFAULT_MIME.get(btype) if isinstance(btype, str) else None


class MediaBlockSanitizerMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Repair or strip historical media content blocks lacking `mime_type`.

    Background: an early version of the engine stored `HumanMessage`s with
    blocks like ``{"type": "audio", "url": "..."}`` — no ``mime_type``. The
    LangGraph checkpointer faithfully replays these on every turn, and
    Gemini's adapter falls back to ``mimetypes.guess_type`` against the raw
    URL (query string included), which silently fails on signed URLs or
    extensions it doesn't know. The result is an ``inlineData`` payload
    with empty ``mimeType`` and the request is rejected with INVALID_ARGUMENT.

    For each historical block we either:
      - attach a guessed (or per-type default) ``mime_type``, so the model
        sees a complete payload, or
      - drop the block entirely when no reasonable mime can be inferred,
        which is safer than sending something the API will refuse.

    The textual ``[Attachments]`` URL list embedded in the original message
    body is preserved, so the model still has the URL reference for
    delegation/recall even when a binary block is dropped.
    """

    @override
    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[AgentContext],
        handler: Callable[[ModelRequest[AgentContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        messages = request.messages
        patched = False
        for i, msg in enumerate(messages):
            if not isinstance(msg, HumanMessage):
                continue
            if not isinstance(msg.content, list):
                continue
            cleaned: list[Any] = []
            modified = False
            for block in msg.content:
                media_block = _as_media_block(block)
                if media_block is None:
                    cleaned.append(block)
                    continue
                if media_block.get("mime_type"):
                    cleaned.append(block)
                    continue
                resolved = _resolve_mime_type(media_block)
                btype = media_block.get("type")
                if resolved is None:
                    modified = True
                    logger.warning(
                        "Dropping historical %s block at msg[%d] — no resolvable mime_type",
                        btype,
                        i,
                    )
                    continue
                modified = True
                cleaned.append({**media_block, "mime_type": resolved})
                logger.info(
                    "Repaired historical %s block at msg[%d] with mime_type=%s",
                    btype,
                    i,
                    resolved,
                )
            if not modified:
                continue
            patched = True
            new_content: Any
            if cleaned:
                new_content = cleaned
            else:
                # All blocks stripped — replace with empty text so the
                # message stays valid for providers that reject empty content.
                new_content = ""
            messages[i] = msg.model_copy(update={"content": new_content})
        if patched:
            request = request.override(messages=messages)
        return await handler(request)


class SafeLLMToolSelectorMiddleware(LLMToolSelectorMiddleware):
    """`LLMToolSelectorMiddleware` that silently drops `always_include` names
    missing from the current request's tool list.

    Upstream raises `ValueError` when any name in `always_include` isn't
    present in `request.tools`. In IntentKit, `ToolBindingMiddleware` drops
    team_only tools per-request, so a pinned name (e.g. `create_post`) may
    legitimately be absent on a guest-context request. Filter to what's
    actually available rather than crashing.
    """

    @override
    def _prepare_selection_request(self, request):  # type: ignore[override]
        if not self.always_include:
            return super()._prepare_selection_request(request)
        available = {t.name for t in request.tools if not isinstance(t, dict)}
        effective = [name for name in self.always_include if name in available]
        if len(effective) == len(self.always_include):
            return super()._prepare_selection_request(request)
        # Temporarily swap `always_include` for this call. Safe because
        # `_prepare_selection_request` is sync with no awaits, so asyncio tasks
        # cannot interleave inside the try/finally block.
        original = self.always_include
        self.always_include = effective
        try:
            return super()._prepare_selection_request(request)
        finally:
            self.always_include = original


__all__ = [
    "DynamicPromptMiddleware",
    "EmptyContentSafetyMiddleware",
    "MediaBlockSanitizerMiddleware",
    "SafeLLMToolSelectorMiddleware",
    "StepTrackingMiddleware",
    "SummarizationMiddleware",
    "ToolBindingMiddleware",
]
