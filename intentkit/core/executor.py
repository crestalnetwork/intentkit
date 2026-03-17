"""Agent executor building and caching.

This module handles:
- Building AI agent executors with LLM, skills, and middleware
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

from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.config.config import config
from intentkit.config.db import get_checkpointer
from intentkit.core.agent import get_agent
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.llm import LLMProvider, create_llm_model
from intentkit.models.llm_picker import pick_summarize_model
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Global variable to cache all agent executors
_agents: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}

# Global dictionaries to cache agent update times
_agents_updated: dict[str, datetime] = {}

# Track when each executor was last accessed, for TTL eviction
_agents_accessed_at: dict[str, datetime] = {}

# Lock to prevent concurrent builds for the same agent
_build_locks: dict[str, asyncio.Lock] = {}
_global_lock = asyncio.Lock()

_EXECUTOR_CACHE_TTL = timedelta(hours=1)


async def build_executor(
    agent: Agent,
    agent_data: AgentData,
    custom_skills: Sequence[BaseTool] = (),
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
        custom_skills (list[BaseTool], optional): Designed for advanced user who directly
            call this function to inject custom skills into the agent tool node.

    Returns:
        CompiledStateGraph: Initialized LangChain agent
    """
    from langchain.agents import create_agent as create_langchain_agent
    from langchain.agents.middleware import (
        ClearToolUsesEdit,
        ContextEditingMiddleware,
        LLMToolSelectorMiddleware,
        ModelRetryMiddleware,
        TodoListMiddleware,
        ToolRetryMiddleware,
    )

    from intentkit.core.middleware import (
        DynamicPromptMiddleware,
        StepTrackingMiddleware,
        SummarizationMiddleware,
        ToolBindingMiddleware,
        TrimMessagesMiddleware,
    )

    # Create the LLM model instance
    llm_model = await create_llm_model(
        model_name=agent.model,
        temperature=agent.temperature if agent.temperature is not None else 0.7,
        frequency_penalty=(
            agent.frequency_penalty if agent.frequency_penalty is not None else 0.0
        ),
        presence_penalty=(
            agent.presence_penalty if agent.presence_penalty is not None else 0.0
        ),
    )

    # ==== Store buffered conversation history in memory.
    try:
        checkpointer = get_checkpointer()
    except RuntimeError:
        checkpointer = InMemorySaver()

    # ==== Load skills
    tools: list[BaseTool | dict[str, Any]] = []
    private_tools: list[BaseTool | dict[str, Any]] = []

    if agent.skills:
        for k, v in agent.skills.items():
            if not v.get("enabled", False):
                continue
            try:
                skill_module = importlib.import_module(f"intentkit.skills.{k}")
                if hasattr(skill_module, "get_skills"):
                    # all
                    skill_tools = await skill_module.get_skills(
                        v, False, agent_id=agent.id, agent=agent
                    )
                    if skill_tools and len(skill_tools) > 0:
                        tools.extend(skill_tools)
                    # private
                    skill_private_tools = await skill_module.get_skills(
                        v, True, agent_id=agent.id, agent=agent
                    )
                    if skill_private_tools and len(skill_private_tools) > 0:
                        private_tools.extend(skill_private_tools)
                else:
                    logger.error("Skill %s does not have get_skills function", k)
            except ImportError as e:
                logger.error("Could not import skill module: %s (%s)", k, e)

    # add custom skills to private tools
    if custom_skills and len(custom_skills) > 0:
        private_tools.extend(custom_skills)

    # add system skills to private tools
    from intentkit.core.system_skills import get_system_skills

    system_skills = get_system_skills(agent)
    # Skip read_webpage for providers that have native search capabilities
    model_provider = llm_model.info.provider
    if model_provider in (LLMProvider.GOOGLE, LLMProvider.OPENAI):
        system_skills = [s for s in system_skills if s.name != "read_webpage"]
    private_tools.extend(system_skills)

    # filter the duplicate tools
    tools = list(
        {
            (tool.name if isinstance(tool, BaseTool) else str(tool.get("name"))): tool
            for tool in tools
        }.values()
    )
    private_tools = list(
        {
            (tool.name if isinstance(tool, BaseTool) else str(tool.get("name"))): tool
            for tool in private_tools
        }.values()
    )

    for tool in private_tools:
        logger.info(
            "[%s] loaded tool: %s",
            agent.id,
            tool.name if isinstance(tool, BaseTool) else tool,
        )

    base_model = await llm_model.create_instance()

    middleware: list[Any] = [
        ToolBindingMiddleware(llm_model, tools, private_tools),
        DynamicPromptMiddleware(agent, agent_data),
        StepTrackingMiddleware(),
        ToolRetryMiddleware(),
        ModelRetryMiddleware(),
    ]

    if agent.enable_todo:
        middleware.append(TodoListMiddleware())

    # Auto-enable LLM tool selector when there are many tools
    if len(private_tools) > 10:
        selector_model_name = pick_summarize_model()
        selector_llm = await create_llm_model(model_name=selector_model_name)
        selector_model = await selector_llm.create_instance()
        middleware.append(LLMToolSelectorMiddleware(model=selector_model))

    # Context editing clears old tool results at 40% context to free space.
    # Note: ContextEditingMiddleware uses wrap_model_call while SummarizationMiddleware
    # uses before_model, so summarization always runs first regardless of list position.
    # The lower threshold (40%) ensures context editing handles moderate growth,
    # while summarization (60-80%) handles extreme cases.
    context_editing_trigger = int(llm_model.info.context_length * 0.4)
    middleware.append(
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=context_editing_trigger,
                    exclude_tools=["ui_show_card", "ui_ask_user"],
                )
            ]
        )
    )

    if agent.short_term_memory_strategy == "trim":
        middleware.append(TrimMessagesMiddleware(max_summary_tokens=2048))
    elif agent.short_term_memory_strategy == "summarize":
        summarize_model_name = pick_summarize_model()
        summarize_llm = await create_llm_model(model_name=summarize_model_name)
        summarize_model = await summarize_llm.create_instance()
        middleware.append(
            SummarizationMiddleware(
                model=summarize_model,
                trigger=[
                    ("fraction", 0.8),
                    ("tokens", int(llm_model.info.context_length * 0.8)),
                ]
                if agent.super_mode
                else [
                    ("fraction", 0.6),
                    ("tokens", int(llm_model.info.context_length * 0.6)),
                ],
            )
        )

    # Credit check is done at conversation start, not per-tool-call.
    # As long as balance is positive, the user gets one conversation opportunity.

    executor = create_langchain_agent(
        model=base_model,
        tools=private_tools,
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
            _agents.pop(aid, None)
            _agents_updated.pop(aid, None)
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
    _agents[aid] = executor
    agent_ts = agent.deployed_at if agent.deployed_at else agent.updated_at
    _agents_updated[aid] = max(agent_ts, agent_data.updated_at)
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
    agent_ts = agent.deployed_at if agent.deployed_at else agent.updated_at
    updated_at = max(agent_ts, agent_data.updated_at)
    # Check if agent needs reinitialization due to updates
    needs_reinit = False
    if agent_id in _agents:
        if agent_id not in _agents_updated or updated_at != _agents_updated[agent_id]:
            needs_reinit = True
            logger.info("Reinitializing agent %s due to updates", agent_id)

    # cold start or needs reinitialization
    cold_start_cost = 0.0
    if (agent_id not in _agents) or needs_reinit:
        lock = await _get_build_lock(agent_id)
        async with lock:
            # Re-check with fresh state after acquiring lock
            still_missing = agent_id not in _agents
            still_stale = agent_id in _agents and (
                agent_id not in _agents_updated
                or updated_at != _agents_updated[agent_id]
            )
            if still_missing or still_stale:
                await build_and_cache_executor(agent_id, agent, agent_data)
                cold_start_cost = time.perf_counter() - start

    _agents_accessed_at[agent_id] = datetime.now(timezone.utc)
    return _agents[agent_id], cold_start_cost
