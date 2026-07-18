"""Agent executor building and caching.

This module handles:
- Building AI agent executors with LLM, tools, and middleware
- Caching executors with timestamp-based invalidation
- Agent executor lifecycle management
"""

# pyright: reportImportCycles=false

import asyncio
import importlib
import logging
import time
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

import httpcore
import httpx
from langchain_core.tools import BaseTool
from langchain_core.tools.base import ToolException
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from openrouter.errors import ResponseValidationError
from pydantic import ValidationError
from pydantic.v1 import ValidationError as ValidationErrorV1

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.config.config import config
from intentkit.config.db import get_checkpointer
from intentkit.core.agent import get_agent
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.llm import LLMProvider, create_llm_model
from intentkit.models.llm_picker import pick_summarize_model
from intentkit.tools.base import IntentKitTool
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Global variable to cache all agent executors
agents: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}

# Global dictionaries to cache agent update times
agents_updated: dict[str, datetime] = {}

# Track when each executor was last accessed, for TTL eviction
_agents_accessed_at: dict[str, datetime] = {}

# Lock to prevent concurrent builds for the same agent
_build_locks: dict[str, asyncio.Lock] = {}
_global_lock = asyncio.Lock()

_EXECUTOR_CACHE_TTL = timedelta(hours=1)


def _should_retry_tool_failure(exc: Exception) -> bool:
    """Retry transient tool failures, but not user-facing tool/validation errors."""
    return not isinstance(exc, (ToolException, ValidationError, ValidationErrorV1))


def _should_retry_model_failure(exc: Exception) -> bool:
    """Retry only transient model API failures.

    Connection drops, timeouts, rate limits, and provider 5xx are worth
    retrying; permanent errors (auth, invalid request, context overflow,
    content policy) are not — they propagate to the engine's error handling.

    The exception chain is walked (explicit ``__cause__``, falling back to
    implicit ``__context__``) because SDKs wrap the telling error: openai/
    anthropic ``APIConnectionError`` carries the httpx error as ``__cause__``,
    and langchain-google-genai wraps 4xx ``ClientError`` (429 included) into a
    ``ChatGoogleGenerativeAIError`` whose status code only survives on the
    cause. ``status_code``/``code``/``response.status_code`` are duck-typed
    for the same reason — one filter must cover the openai, anthropic, and
    google exception families. OpenRouter needs the explicit
    ``ResponseValidationError`` case below on top of that: a stream truncated
    mid-body surfaces as a would-be parse failure that status alone cannot
    tell apart from a genuine, permanent schema mismatch.
    """
    cause: BaseException | None = exc
    seen: set[int] = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(
            cause,
            (
                ConnectionError,
                TimeoutError,
                httpx.TransportError,
                httpcore.TimeoutException,
                httpcore.NetworkError,
                httpcore.ProtocolError,
            ),
        ):
            return True
        if isinstance(cause, ResponseValidationError):
            # A 2xx whose body stopped mid-JSON — the upstream stream dropped.
            # The SDK's own retries never see it: parsing happens after the
            # HTTP layer already succeeded. Two sibling cases deliberately fall
            # through to the status filter instead: a body that parsed but
            # failed the schema (SDK/API drift, permanent), and any non-2xx,
            # since the SDK unmarshals error bodies too and a truncated 402
            # must stay as final as an intact one.
            if 200 <= cause.status_code < 300 and not isinstance(
                cause.__cause__, (ValidationError, ValidationErrorV1)
            ):
                return True
        candidates = (
            getattr(cause, "status_code", None),
            getattr(cause, "code", None),
            getattr(getattr(cause, "response", None), "status_code", None),
        )
        for status in candidates:
            if isinstance(status, str) and status.isdigit():
                status = int(status)
            if isinstance(status, int) and (status in (408, 429) or status >= 500):
                return True
        nxt = cause.__cause__
        if nxt is None and not cause.__suppress_context__:
            nxt = cause.__context__
        cause = nxt
    return False


async def build_executor(
    agent: Agent,
    agent_data: AgentData,
    custom_tools: Sequence[BaseTool] = (),
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build an AI agent executor with specified configuration and tools.

    This function:
    1. Initializes LLM with specified model
    2. Loads and configures requested tools
    3. Sets up PostgreSQL-based memory
    4. Creates and returns the compiled executor

    Args:
        agent (Agent): Agent configuration object
        agent_data (AgentData): Agent data object
        custom_tools (list[BaseTool], optional): Designed for advanced user who directly
            call this function to inject custom tools into the agent tool node.

    Returns:
        CompiledStateGraph: Initialized LangChain agent
    """
    from langchain.agents import create_agent as create_langchain_agent
    from langchain.agents.middleware import (
        ModelRetryMiddleware,
        ToolRetryMiddleware,
    )
    from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

    from intentkit.core.middleware import (
        DynamicPromptMiddleware,
        EmptyContentSafetyMiddleware,
        MediaBlockSanitizerMiddleware,
        StepTrackingMiddleware,
        TodoMiddleware,
        ToolBindingMiddleware,
    )
    from intentkit.core.summarization import SummarizationMiddleware

    # Create the LLM model instance
    llm_model = await create_llm_model(
        model_name=agent.model,
        reasoning_effort=agent.reasoning_effort,
    )

    # ==== Store buffered conversation history in memory.
    try:
        checkpointer = get_checkpointer()
    except RuntimeError:
        checkpointer = InMemorySaver()

    # ==== Load tools into ONE list. Per-request gating happens in
    # ToolBindingMiddleware: tools marked team_only (publishing, signing,
    # spending) are dropped when a guest of a published agent is talking.
    tools: list[BaseTool | dict[str, Any]] = []

    if agent.tools:
        from intentkit.core.agent.tool_registry import group_tool_names_by_category

        for category, names in group_tool_names_by_category(agent.tools).items():
            try:
                tool_module = importlib.import_module(f"intentkit.tools.{category}")
                if hasattr(tool_module, "get_tools"):
                    tool_tools = await tool_module.get_tools(
                        names, agent_id=agent.id, agent=agent
                    )
                    if tool_tools and len(tool_tools) > 0:
                        tools.extend(tool_tools)
                else:
                    logger.error("Tool %s does not have get_tools function", category)
            except ImportError as e:
                logger.error("Could not import tool module: %s (%s)", category, e)

    # custom tools (lead engine): lead agents are never public
    if custom_tools and len(custom_tools) > 0:
        tools.extend(custom_tools)

    # add system tools — each conditionally based on agent config and provider
    from intentkit.core.system_tools import (
        call_agent,
        create_activity,
        create_post,
        current_time,
        get_post,
        read_webpage_cloudflare,
        recent_activities,
        recent_posts,
        store_image,
        ui_ask_user,
        ui_show_card,
        update_memory,
        web_search,
        write_todos,
    )

    model_provider = llm_model.info.provider

    # current_time: system tool used by every provider. We intentionally do
    # NOT use OpenRouter's openrouter:datetime server tool, so all agents share
    # the same time behaviour (formatted time plus a Unix timestamp).
    tools.append(current_time)

    # interactive UI tools (cards, choice buttons): every chat surface renders
    # them, so they are bound for all agents rather than user-selected. They
    # are interactive_only — ToolBindingMiddleware drops them per request for
    # cron-triggered runs and sub-agent calls, where no live user is watching.
    tools.append(ui_show_card)
    tools.append(ui_ask_user)

    # call_agent: only when sub-agents are configured. Open to guests —
    # sub-agent runs recompute their own access context per message.
    if agent.sub_agents:
        tools.append(call_agent)

    # write_todos: task planning for complex multi-step requests, always on
    # for live conversations. Like the UI tools it is interactive_only —
    # ToolBindingMiddleware drops it for cron-triggered runs (single-shot,
    # facts carry via task memory) and sub-agent runs (the plan belongs to
    # the calling agent). TodoMiddleware carries the matching prompt
    # guidance and lifecycle, gated the same way.
    tools.append(write_todos)

    # activity tools: enabled by default (create_activity is team_only)
    if agent.is_activity_enabled:
        tools.append(create_activity)
        tools.append(recent_activities)

    # post tools: enabled by default (create_post is team_only)
    if agent.is_post_enabled:
        tools.append(create_post)
        tools.append(get_post)
        tools.append(recent_posts)

    # scoped long-term memory is always on: guests update their own rows
    # (their user memory and their team's memory of this agent)
    tools.append(update_memory)

    # search-related tools based on provider
    extra_llm_params: dict[str, Any] = {}
    if agent.search_internet:
        if model_provider == LLMProvider.OPENAI:
            search_tools: list[dict[str, Any]] = [{"type": "web_search"}]
            tools.extend(search_tools)
        elif model_provider == LLMProvider.XAI:
            search_tools = [{"type": "web_search"}, {"type": "x_search"}]
            tools.extend(search_tools)
        elif model_provider == LLMProvider.GOOGLE:
            search_tools = [{"google_search": {}}, {"url_context": {}}]
            tools.extend(search_tools)
        else:
            # Everyone else uses our own client-side web tools: deepseek,
            # minimax, mimo_plan, ollama, *_compatible, and all OpenRouter
            # models. OpenRouter is deliberately here rather than on its
            # server-side web_search/web_fetch tools: those corrupt tool
            # calling on continuation turns — every routed model leaks its
            # native tool-call tokens as plain text (DeepSeek DSML, MiMo
            # `<function=>`, GPT `to=functions.`) instead of a structured
            # call, so multi-step tasks never complete. Our client-side
            # web_search + reader avoid that path. Each self-checks its own
            # config and raises a clear error if unconfigured.
            tools.extend([web_search, read_webpage_cloudflare])

        # store_image: paired with the search/reader tools above so the
        # agent can persist URLs it discovered online. Registered for every
        # provider — no native LLM search backs images into our S3, so the
        # capability is provider-independent inside the search-enabled
        # branch. Gated additionally on S3 config so we don't expose a tool
        # that will always fail.
        if config.aws_s3_bucket and config.aws_s3_cdn_url:
            tools.append(store_image)

    # filter out unavailable tools
    tools = [t for t in tools if not isinstance(t, IntentKitTool) or t.available()]

    # filter the duplicate tools
    def _tool_key(tool: BaseTool | dict[str, Any]) -> str:
        if isinstance(tool, BaseTool):
            return tool.name
        return str(tool.get("name") or tool.get("type") or tool)

    tools = list({_tool_key(t): t for t in tools}.values())

    for tool in tools:
        logger.info(
            "[%s] loaded tool: %s",
            agent.id,
            tool.name if isinstance(tool, BaseTool) else tool,
        )

    base_model = await llm_model.create_instance()

    middleware: list[Any] = [
        ToolBindingMiddleware(llm_model, tools, extra_llm_params),
        DynamicPromptMiddleware(agent, agent_data),
        EmptyContentSafetyMiddleware(),
        MediaBlockSanitizerMiddleware(),
        StepTrackingMiddleware(),
        ToolRetryMiddleware(retry_on=_should_retry_tool_failure),
        # The SDK clients already retry pre-stream failures (max_retries=3 in
        # llm.py); this layer exists for what they won't retry — errors after
        # streaming began. retry_on keeps it to transient failures, and
        # on_failure="error" propagates terminal ones to the engine's error
        # handling instead of recording them as a fake assistant message.
        ModelRetryMiddleware(
            max_retries=2,
            retry_on=_should_retry_model_failure,
            on_failure="error",
        ),
        TodoMiddleware(),
    ]

    # Anthropic prompt caching: 5m ephemeral cache slashes input-token cost on
    # long system prompts + repeated history. No-op for non-Anthropic providers.
    # Must come after TodoMiddleware in this list: the cache breakpoint tags
    # the last system-message block, so the todo guidance/snapshot block has
    # to be appended before the tag is placed to be covered by the cache.
    if model_provider == LLMProvider.ANTHROPIC_COMPATIBLE:
        middleware.append(AnthropicPromptCachingMiddleware())

    # History growth is handled solely by SummarizationMiddleware (per-model
    # thresholds and idle-time tiers: LLMModelInfo.compress_thresholds and
    # intentkit/core/summarization.py). Upstream ContextEditingMiddleware was
    # removed: its approximate token counting (4 chars/token, tuned for
    # English) put the nominal 40%-of-context trigger above the compression
    # thresholds for CJK conversations, and its per-request ephemeral edits
    # deep-copied the whole history every model call while the sliding
    # keep-window broke the Anthropic prompt cache each turn.
    summarize_llm = await create_llm_model(model_name=pick_summarize_model())
    middleware.append(
        SummarizationMiddleware(
            model_info=llm_model.info,
            summary_model=await summarize_llm.create_instance(),
            summary_model_info=summarize_llm.info,
        )
    )

    # Credit check is done at conversation start, not per-tool-call.
    # As long as balance is positive, the user gets one conversation opportunity.

    executor = create_langchain_agent(
        model=base_model,
        tools=tools,
        middleware=middleware,
        state_schema=AgentState,
        context_schema=AgentContext,
        checkpointer=checkpointer,
        debug=config.debug_checkpoint,
        name=agent.id,
    )

    return executor


async def _get_build_lock(agent_id: str) -> asyncio.Lock:
    """Get or create a per-agent build lock."""
    async with _global_lock:
        if agent_id not in _build_locks:
            _build_locks[agent_id] = asyncio.Lock()
        return _build_locks[agent_id]


def _cleanup_cache() -> None:
    """Evict expired executor cache entries based on last access time."""
    now = datetime.now(timezone.utc)
    expired_before = now - _EXECUTOR_CACHE_TTL
    for aid in list(_agents_accessed_at):
        if _agents_accessed_at[aid] < expired_before:
            agents.pop(aid, None)
            agents_updated.pop(aid, None)
            _agents_accessed_at.pop(aid, None)
            _build_locks.pop(aid, None)
            logger.debug("Evicted expired executor cache for %s", aid)


async def build_and_cache_executor(
    aid: str, agent: Agent, agent_data: AgentData
) -> None:
    """Build an agent executor and cache it with timestamp tracking.

    This function:
    1. Builds the executor from agent config and data
    2. Caches the executor
    3. Tracks the latest update timestamp from both agent and agent_data

    Args:
        aid: Agent ID
        agent: Agent configuration object
        agent_data: Agent data object (wallet, API keys, credentials)
    """
    executor = await build_executor(agent, agent_data)
    agents[aid] = executor
    agents_updated[aid] = max(agent.updated_at, agent_data.updated_at)
    _agents_accessed_at[aid] = datetime.now(timezone.utc)


async def agent_executor(
    agent_id: str,
) -> tuple[CompiledStateGraph[Any, Any, Any, Any], float]:
    start = time.perf_counter()

    # Opportunistic TTL cleanup (same pattern as manager cache)
    _cleanup_cache()

    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )
    agent_data = await AgentData.get(agent_id)
    updated_at = max(agent.updated_at, agent_data.updated_at)
    # Check if agent needs reinitialization due to updates
    needs_reinit = False
    if agent_id in agents:
        if agent_id not in agents_updated or updated_at != agents_updated[agent_id]:
            needs_reinit = True
            logger.info("Reinitializing agent %s due to updates", agent_id)

    # cold start or needs reinitialization
    cold_start_cost = 0.0
    if (agent_id not in agents) or needs_reinit:
        lock = await _get_build_lock(agent_id)
        async with lock:
            # Re-check with fresh state after acquiring lock
            still_missing = agent_id not in agents
            still_stale = agent_id in agents and (
                agent_id not in agents_updated or updated_at != agents_updated[agent_id]
            )
            if still_missing or still_stale:
                await build_and_cache_executor(agent_id, agent, agent_data)
                cold_start_cost = time.perf_counter() - start

    _agents_accessed_at[agent_id] = datetime.now(timezone.utc)
    return agents[agent_id], cold_start_cost
