"""AI Agent Management Module.

This module provides functionality for initializing and executing AI agents. It handles:
- Agent initialization with LangChain
- Tool and skill management
- Agent execution and response handling
- Memory management with PostgreSQL
- Integration with CDP and Twitter

The module uses a global cache to store initialized agents for better performance.
"""

import importlib
import logging
import re
import textwrap
import time
import traceback
from datetime import datetime
from typing import Any

import sqlalchemy
from epyxid import XID
from langchain.agents import create_agent as create_langchain_agent
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
)
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError

from intentkit.abstracts.graph import AgentContext, AgentError, AgentState
from intentkit.config.config import config
from intentkit.core.agent import get_agent
from intentkit.core.chat import clear_thread_memory
from intentkit.core.credit import expense_message, expense_skill
from intentkit.core.middleware import (
    CreditCheckMiddleware,
    DynamicPromptMiddleware,
    SummarizationMiddleware,
    ToolBindingMiddleware,
    TrimMessagesMiddleware,
)
from intentkit.core.prompt import explain_prompt
from intentkit.models.agent import Agent, AgentTable
from intentkit.models.agent_data import AgentData, AgentQuota
from intentkit.models.app_setting import AppSetting, SystemMessageType
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageSkillCall,
)
from intentkit.models.credit import CreditAccount, OwnerType
from intentkit.models.db import (
    get_checkpointer,
    get_session,
)
from intentkit.models.llm import LLMModelInfo, create_llm_model
from intentkit.models.skill import AgentSkillData, ChatSkillData, Skill
from intentkit.models.user import User
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# Global variable to cache all agent executors
_agents: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}

# Global dictionaries to cache agent update times
_agents_updated: dict[str, datetime] = {}


def _extract_text_content(content: object) -> str:
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text")
                ty = item.get("type")
                if t is not None and (ty == "text" or ty is None):
                    texts.append(t)
            elif isinstance(item, str):
                texts.append(item)
        return "".join(texts)
    if isinstance(content, dict):
        if content.get("type") == "text" and "text" in content:
            return content["text"]
        if "text" in content:
            return content["text"]
        return ""
    if isinstance(content, str):
        return content
    return ""


async def build_agent(
    agent: Agent, agent_data: AgentData, custom_skills: list[BaseTool] = []
) -> CompiledStateGraph[AgentState, AgentContext, Any, Any]:
    """Build an AI agent with specified configuration and tools.

    This function:
    1. Initializes LLM with specified model
    2. Loads and configures requested tools
    3. Sets up PostgreSQL-based memory
    4. Creates and returns the agent

    Args:
        agent (Agent): Agent configuration object
        agent_data (AgentData): Agent data object
        custom_skills (list[BaseTool], optional): Designed for advanced user who directly
            call this function to inject custom skills into the agent tool node.

    Returns:
        CompiledStateGraph: Initialized LangChain agent
    """

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
                    logger.error(f"Skill {k} does not have get_skills function")
            except ImportError as e:
                logger.error(f"Could not import skill module: {k} ({e})")

    # add custom skills to private tools
    if custom_skills and len(custom_skills) > 0:
        private_tools.extend(custom_skills)

    # filter the duplicate tools
    tools = list({tool.name: tool for tool in tools}.values())
    private_tools = list({tool.name: tool for tool in private_tools}.values())

    for tool in private_tools:
        logger.info(
            f"[{agent.id}] loaded tool: {tool.name if isinstance(tool, BaseTool) else tool}"
        )

    base_model = await llm_model.create_instance()

    middleware = [
        ToolBindingMiddleware(llm_model, tools, private_tools),
        DynamicPromptMiddleware(agent, agent_data),
    ]

    if agent.short_term_memory_strategy == "trim":
        middleware.append(TrimMessagesMiddleware(max_summary_tokens=2048))
    elif agent.short_term_memory_strategy == "summarize":
        summarize_llm = await create_llm_model(model_name="gpt-5-mini")
        summarize_model = await summarize_llm.create_instance()
        middleware.append(
            SummarizationMiddleware(
                model=summarize_model,
                max_tokens_before_summary=llm_model.info.context_length // 2,
            )
        )

    if config.payment_enabled:
        middleware.append(CreditCheckMiddleware())

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


async def create_agent(
    agent: Agent,
) -> CompiledStateGraph[AgentState, AgentContext, Any, Any]:
    """Create an AI agent with specified configuration and tools.

    This function maintains backward compatibility by calling build_agent internally.

    Args:
        agent (Agent): Agent configuration object
        is_private (bool, optional): Flag indicating whether the agent is private. Defaults to False.

    Returns:
        CompiledStateGraph: Initialized LangChain agent
    """
    agent_data = await AgentData.get(agent.id)
    return await build_agent(agent, agent_data)


async def initialize_agent(aid):
    """Initialize an AI agent with specified configuration and tools.

    This function:
    1. Loads agent configuration from database
    2. Uses create_agent to build the agent
    3. Caches the agent

    Args:
        aid (str): Agent ID to initialize
        is_private (bool, optional): Flag indicating whether the agent is private. Defaults to False.

    Returns:
        Agent: Initialized LangChain agent

    Raises:
        HTTPException: If agent not found (404) or database error (500)
    """
    # get the agent from the database
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    # Create the agent using the new create_agent function
    executor = await create_agent(agent)

    # Cache the agent executor
    _agents[aid] = executor
    _agents_updated[aid] = agent.deployed_at if agent.deployed_at else agent.updated_at


async def agent_executor(
    agent_id: str,
) -> tuple[CompiledStateGraph[AgentState, AgentContext, Any, Any], float]:
    start = time.perf_counter()
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )
    updated_at = agent.deployed_at if agent.deployed_at else agent.updated_at
    # Check if agent needs reinitialization due to updates
    needs_reinit = False
    if agent_id in _agents:
        if agent_id not in _agents_updated or updated_at != _agents_updated[agent_id]:
            needs_reinit = True
            logger.info(f"Reinitializing agent {agent_id} due to updates")

    # cold start or needs reinitialization
    cold_start_cost = 0.0
    if (agent_id not in _agents) or needs_reinit:
        await initialize_agent(agent_id)
        cold_start_cost = time.perf_counter() - start
    return _agents[agent_id], cold_start_cost


async def stream_agent(message: ChatMessageCreate):
    """
    Stream agent execution results as an async generator.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        message (ChatMessageCreate): The chat message containing agent_id, chat_id, and message content

    Yields:
        ChatMessage: Individual response messages including timing information
    """
    agent = await get_agent(message.agent_id)
    executor, cold_start_cost = await agent_executor(message.agent_id)
    message.cold_start_cost = cold_start_cost
    async for chat_message in stream_agent_raw(message, agent, executor):
        yield chat_message


async def stream_agent_raw(
    message: ChatMessageCreate,
    agent: Agent,
    executor: CompiledStateGraph[AgentState, AgentContext, Any, Any],
):
    start = time.perf_counter()
    # make sure reply_to is set
    message.reply_to = message.id

    # save input message first
    user_message = await message.save()

    # temporary debug logging for telegram messages
    if user_message.author_type == AuthorType.TELEGRAM:
        logger.info(
            f"[TELEGRAM DEBUG] Agent: {user_message.agent_id} | Chat: {user_message.chat_id} | Message: {user_message.message}"
        )

    if re.search(
        r"(@clear|/clear)(?!\w)",
        user_message.message.strip(),
        re.IGNORECASE,
    ):
        await clear_thread_memory(user_message.agent_id, user_message.chat_id)

        confirmation_message = ChatMessageCreate(
            id=str(XID()),
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            author_type=AuthorType.AGENT,
            model=agent.model,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            message="Memory in context has been cleared.",
            time_cost=time.perf_counter() - start,
        )

        yield await confirmation_message.save()
        return

    model = await LLMModelInfo.get(agent.model)

    payment_enabled = config.payment_enabled

    # check user balance
    if payment_enabled:
        if not user_message.user_id or not agent.owner:
            raise IntentKitAPIError(
                500,
                "PaymentError",
                "Payment is enabled but user_id or agent owner is not set",
            )
        if agent.fee_percentage and agent.fee_percentage > 100:
            owner = await User.get(agent.owner)
            if owner and agent.fee_percentage > 100 + owner.nft_count * 10:
                error_message_create = await ChatMessageCreate.from_system_message(
                    SystemMessageType.SERVICE_FEE_ERROR,
                    agent_id=user_message.agent_id,
                    chat_id=user_message.chat_id,
                    user_id=user_message.user_id,
                    author_id=user_message.agent_id,
                    thread_type=user_message.author_type,
                    reply_to=user_message.id,
                    time_cost=time.perf_counter() - start,
                )
                error_message = await error_message_create.save()
                yield error_message
                return
        # payer
        payer = user_message.user_id
        if user_message.author_type in [
            AuthorType.TELEGRAM,
            AuthorType.DISCORD,
            AuthorType.TWITTER,
            AuthorType.API,
            AuthorType.X402,
        ]:
            payer = agent.owner
        # user account
        user_account = await CreditAccount.get_or_create(OwnerType.USER, payer)
        # quota
        quota = await AgentQuota.get(message.agent_id)
        # payment settings
        payment_settings = await AppSetting.payment()
        # agent abuse check
        abuse_check = True
        if (
            payment_settings.agent_whitelist_enabled
            and agent.id in payment_settings.agent_whitelist
        ):
            abuse_check = False
        if abuse_check and payer != agent.owner and user_account.free_credits > 0:
            if quota and quota.free_income_daily > 24000:
                error_message_create = await ChatMessageCreate.from_system_message(
                    SystemMessageType.DAILY_USAGE_LIMIT_EXCEEDED,
                    agent_id=user_message.agent_id,
                    chat_id=user_message.chat_id,
                    user_id=user_message.user_id,
                    author_id=user_message.agent_id,
                    thread_type=user_message.author_type,
                    reply_to=user_message.id,
                    time_cost=time.perf_counter() - start,
                )
                error_message = await error_message_create.save()
                yield error_message
                return
        # avg cost
        avg_count = 1
        if quota and quota.avg_action_cost > 0:
            avg_count = quota.avg_action_cost
        if not user_account.has_sufficient_credits(avg_count):
            error_message_create = await ChatMessageCreate.from_system_message(
                SystemMessageType.INSUFFICIENT_BALANCE,
                agent_id=user_message.agent_id,
                chat_id=user_message.chat_id,
                user_id=user_message.user_id,
                author_id=user_message.agent_id,
                thread_type=user_message.author_type,
                reply_to=user_message.id,
                time_cost=time.perf_counter() - start,
            )
            error_message = await error_message_create.save()
            yield error_message
            return

    is_private = False
    if user_message.user_id == agent.owner:
        is_private = True

    last = start

    # Extract images from attachments
    image_urls = []
    if user_message.attachments:
        image_urls = [
            att["url"]
            for att in user_message.attachments
            if "type" in att and att["type"] == "image" and "url" in att
        ]

    # Process input message to handle @skill patterns
    input_message = await explain_prompt(user_message.message)

    # super mode
    recursion_limit = 30
    if (
        re.search(r"@super\b", input_message)
        or user_message.super_mode
        or agent.has_super()
    ):
        recursion_limit = 300
        input_message = re.sub(r"@super\b", "", input_message).strip()

    # llm native search
    search = user_message.search_mode if user_message.search_mode is not None else False
    if re.search(r"@search\b", input_message) or re.search(r"@web\b", input_message):
        search = True

    # content to llm
    messages = [
        HumanMessage(content=input_message),
    ]
    # if the model doesn't natively support image parsing, add the image URLs to the message
    if image_urls:
        if (
            agent.has_image_parser_skill(is_private=is_private)
            and not model.supports_image_input
        ):
            image_urls_text = "\n".join(image_urls)
            input_message += f"\n\nImages:\n{image_urls_text}"
            messages = [
                HumanMessage(content=input_message),
            ]
        else:
            # anyway, pass it directly to LLM
            messages.extend(
                [
                    HumanMessage(
                        content={"type": "image_url", "image_url": {"url": image_url}}
                    )
                    for image_url in image_urls
                ]
            )

    # stream config
    thread_id = f"{user_message.agent_id}-{user_message.chat_id}"
    stream_config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": recursion_limit,
    }

    def get_agent() -> Agent:
        return agent

    context = AgentContext(
        agent_id=user_message.agent_id,
        get_agent=get_agent,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        app_id=user_message.app_id,
        entrypoint=user_message.author_type,
        is_private=is_private,
        search=search,
        payer=payer if payment_enabled else None,
    )

    # run
    cached_tool_step = None
    try:
        async for chunk in executor.astream(
            {"messages": messages},
            context=context,
            config=stream_config,
            stream_mode=["updates", "custom"],
        ):
            this_time = time.perf_counter()
            logger.debug(f"stream chunk: {chunk}", extra={"thread_id": thread_id})

            if isinstance(chunk, tuple) and len(chunk) == 2:
                event_kind, payload = chunk
                chunk = payload

            if isinstance(chunk, dict) and "credit_check" in chunk:
                credit_payload = chunk.get("credit_check", {})
                content = credit_payload.get("message")
                if content:
                    credit_message_create = ChatMessageCreate(
                        id=str(XID()),
                        agent_id=user_message.agent_id,
                        chat_id=user_message.chat_id,
                        user_id=user_message.user_id,
                        author_id=user_message.agent_id,
                        author_type=AuthorType.AGENT,
                        model=agent.model,
                        thread_type=user_message.author_type,
                        reply_to=user_message.id,
                        message=content,
                        input_tokens=0,
                        output_tokens=0,
                        time_cost=this_time - last,
                    )
                    last = this_time
                    credit_message = await credit_message_create.save()
                    yield credit_message

                    error_message_create = await ChatMessageCreate.from_system_message(
                        SystemMessageType.INSUFFICIENT_BALANCE,
                        agent_id=user_message.agent_id,
                        chat_id=user_message.chat_id,
                        user_id=user_message.user_id,
                        author_id=user_message.agent_id,
                        thread_type=user_message.author_type,
                        reply_to=user_message.id,
                        time_cost=0,
                    )
                    error_message = await error_message_create.save()
                    yield error_message
                return

            if not isinstance(chunk, dict):
                continue

            if "model" in chunk and "messages" in chunk["model"]:
                if len(chunk["model"]["messages"]) != 1:
                    logger.error(
                        "unexpected model message: " + str(chunk["model"]["messages"]),
                        extra={"thread_id": thread_id},
                    )
                msg = chunk["model"]["messages"][0]
                has_tools = hasattr(msg, "tool_calls") and bool(msg.tool_calls)
                if has_tools:
                    cached_tool_step = msg
                content = (
                    _extract_text_content(msg.content)
                    if hasattr(msg, "content")
                    else ""
                )
                if content and not has_tools:
                    chat_message_create = ChatMessageCreate(
                        id=str(XID()),
                        agent_id=user_message.agent_id,
                        chat_id=user_message.chat_id,
                        user_id=user_message.user_id,
                        author_id=user_message.agent_id,
                        author_type=AuthorType.AGENT,
                        model=agent.model,
                        thread_type=user_message.author_type,
                        reply_to=user_message.id,
                        message=content,
                        input_tokens=(
                            msg.usage_metadata.get("input_tokens", 0)
                            if hasattr(msg, "usage_metadata") and msg.usage_metadata
                            else 0
                        ),
                        output_tokens=(
                            msg.usage_metadata.get("output_tokens", 0)
                            if hasattr(msg, "usage_metadata") and msg.usage_metadata
                            else 0
                        ),
                        time_cost=this_time - last,
                    )
                    last = this_time
                    async with get_session() as session:
                        if payment_enabled:
                            amount = await model.calculate_cost(
                                chat_message_create.input_tokens,
                                chat_message_create.output_tokens,
                            )

                            if (
                                hasattr(msg, "additional_kwargs")
                                and msg.additional_kwargs
                            ):
                                tool_outputs = msg.additional_kwargs.get(
                                    "tool_outputs", []
                                )
                                for tool_output in tool_outputs:
                                    if tool_output.get("type") == "web_search_call":
                                        logger.info(
                                            f"[{user_message.agent_id}] Found web_search_call in additional_kwargs"
                                        )
                                        amount += 35
                                        break
                            credit_event = await expense_message(
                                session,
                                payer,
                                chat_message_create.id,
                                user_message.id,
                                amount,
                                agent,
                            )
                            logger.info(
                                f"[{user_message.agent_id}] expense message: {amount}"
                            )
                            chat_message_create.credit_event_id = credit_event.id
                            chat_message_create.credit_cost = credit_event.total_amount
                        chat_message = await chat_message_create.save_in_session(
                            session
                        )
                        await session.commit()
                        yield chat_message
            elif "tools" in chunk and "messages" in chunk["tools"]:
                if not cached_tool_step:
                    logger.error(
                        "unexpected tools message: " + str(chunk["tools"]),
                        extra={"thread_id": thread_id},
                    )
                    continue
                skill_calls = []
                cached_attachments = []
                have_first_call_in_cache = False  # tool node emit every tool call
                for msg in chunk["tools"]["messages"]:
                    if not hasattr(msg, "tool_call_id"):
                        logger.error(
                            "unexpected tools message: " + str(chunk["tools"]),
                            extra={"thread_id": thread_id},
                        )
                        continue
                    for call_index, call in enumerate(cached_tool_step.tool_calls):
                        if call["id"] == msg.tool_call_id:
                            if call_index == 0:
                                have_first_call_in_cache = True
                            skill_call: ChatMessageSkillCall = {
                                "id": msg.tool_call_id,
                                "name": call["name"],
                                "parameters": call["args"],
                                "success": True,
                            }
                            status = getattr(msg, "status", None)
                            if status == "error":
                                skill_call["success"] = False
                                skill_call["error_message"] = str(msg.content)
                            else:
                                if config.debug:
                                    skill_call["response"] = str(msg.content)
                                else:
                                    skill_call["response"] = textwrap.shorten(
                                        str(msg.content), width=1000, placeholder="..."
                                    )
                                artifact = getattr(msg, "artifact", None)
                                if artifact:
                                    cached_attachments.extend(artifact)
                            skill_calls.append(skill_call)
                            break
                skill_message_create = ChatMessageCreate(
                    id=str(XID()),
                    agent_id=user_message.agent_id,
                    chat_id=user_message.chat_id,
                    user_id=user_message.user_id,
                    author_id=user_message.agent_id,
                    author_type=AuthorType.SKILL,
                    model=agent.model,
                    thread_type=user_message.author_type,
                    reply_to=user_message.id,
                    message="",
                    skill_calls=skill_calls,
                    attachments=cached_attachments,
                    input_tokens=(
                        cached_tool_step.usage_metadata.get("input_tokens", 0)
                        if hasattr(cached_tool_step, "usage_metadata")
                        and cached_tool_step.usage_metadata
                        and have_first_call_in_cache
                        else 0
                    ),
                    output_tokens=(
                        cached_tool_step.usage_metadata.get("output_tokens", 0)
                        if hasattr(cached_tool_step, "usage_metadata")
                        and cached_tool_step.usage_metadata
                        and have_first_call_in_cache
                        else 0
                    ),
                    time_cost=this_time - last,
                )
                last = this_time
                async with get_session() as session:
                    if payment_enabled:
                        if have_first_call_in_cache:
                            message_amount = await model.calculate_cost(
                                skill_message_create.input_tokens,
                                skill_message_create.output_tokens,
                            )
                            message_payment_event = await expense_message(
                                session,
                                payer,
                                skill_message_create.id,
                                user_message.id,
                                message_amount,
                                agent,
                            )
                            skill_message_create.credit_event_id = (
                                message_payment_event.id
                            )
                            skill_message_create.credit_cost = (
                                message_payment_event.total_amount
                            )
                        for skill_call in skill_calls:
                            if not skill_call["success"]:
                                continue
                            skill = await Skill.get(skill_call["name"])
                            if not skill:
                                continue
                            payment_event = await expense_skill(
                                session,
                                payer,
                                skill_message_create.id,
                                user_message.id,
                                skill_call["id"],
                                skill_call["name"],
                                agent,
                            )
                            skill_call["credit_event_id"] = payment_event.id
                            skill_call["credit_cost"] = payment_event.total_amount
                            logger.info(
                                f"[{user_message.agent_id}] skill payment: {skill_call}"
                            )
                    skill_message_create.skill_calls = skill_calls
                    skill_message = await skill_message_create.save_in_session(session)
                    await session.commit()
                    yield skill_message
            else:
                for node_name, update in chunk.items():
                    if (
                        node_name.endswith("CreditCheckMiddleware.after_model")
                        and isinstance(update, dict)
                        and update.get("error") == AgentError.INSUFFICIENT_CREDITS
                    ):
                        ai_messages = [
                            message
                            for message in update.get("messages", [])
                            if isinstance(message, BaseMessage)
                        ]
                        content = ""
                        if ai_messages:
                            content = _extract_text_content(ai_messages[-1].content)
                        post_model_message_create = ChatMessageCreate(
                            id=str(XID()),
                            agent_id=user_message.agent_id,
                            chat_id=user_message.chat_id,
                            user_id=user_message.user_id,
                            author_id=user_message.agent_id,
                            author_type=AuthorType.AGENT,
                            model=agent.model,
                            thread_type=user_message.author_type,
                            reply_to=user_message.id,
                            message=content,
                            input_tokens=0,
                            output_tokens=0,
                            time_cost=this_time - last,
                        )
                        last = this_time
                        post_model_message = await post_model_message_create.save()
                        yield post_model_message

                        error_message_create = (
                            await ChatMessageCreate.from_system_message(
                                SystemMessageType.INSUFFICIENT_BALANCE,
                                agent_id=user_message.agent_id,
                                chat_id=user_message.chat_id,
                                user_id=user_message.user_id,
                                author_id=user_message.agent_id,
                                thread_type=user_message.author_type,
                                reply_to=user_message.id,
                                time_cost=0,
                            )
                        )
                        error_message = await error_message_create.save()
                        yield error_message
                        return
    except SQLAlchemyError as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id},
        )
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            time_cost=time.perf_counter() - start,
        )
        error_message = await error_message_create.save()
        yield error_message
        return
    except GraphRecursionError as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"reached recursion limit: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id, "agent_id": user_message.agent_id},
        )
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.STEP_LIMIT_EXCEEDED,
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            time_cost=time.perf_counter() - start,
        )
        error_message = await error_message_create.save()
        yield error_message
        return
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id, "agent_id": user_message.agent_id},
        )
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            agent_id=user_message.agent_id,
            chat_id=user_message.chat_id,
            user_id=user_message.user_id,
            author_id=user_message.agent_id,
            thread_type=user_message.author_type,
            reply_to=user_message.id,
            time_cost=time.perf_counter() - start,
        )
        error_message = await error_message_create.save()
        yield error_message
        await clear_thread_memory(user_message.agent_id, user_message.chat_id)
        return


async def execute_agent(message: ChatMessageCreate) -> list[ChatMessage]:
    """
    Execute an agent with the given prompt and return response lines.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        message (ChatMessageCreate): The chat message containing agent_id, chat_id, and message content
        debug (bool): Enable debug mode, will save the skill results

    Returns:
        list[ChatMessage]: Formatted response lines including timing information
    """
    resp = []
    async for chat_message in stream_agent(message):
        resp.append(chat_message)
    return resp


async def clean_agent_memory(
    agent_id: str,
    chat_id: str = "",
    clean_agent: bool = False,
    clean_skill: bool = False,
) -> str:
    """
    Clean an agent's memory with the given prompt and return response.

    This function:
    1. Cleans the agents skills data.
    2. Cleans the thread skills data.
    3. Cleans the graph checkpoint data.
    4. Cleans the graph checkpoint_writes data.
    5. Cleans the graph checkpoint_blobs data.

    Args:
        agent_id (str): Agent ID
        chat_id (str): Thread ID for the agent memory cleanup
        clean_agent (bool): Whether to clean agent's memory data
        clean_skill (bool): Whether to clean skills memory data

    Returns:
        str: Successful response message.
    """
    # get the agent from the database
    try:
        if not clean_skill and not clean_agent:
            raise IntentKitAPIError(
                status_code=400,
                key="InvalidCleanupParameters",
                message="at least one of skills data or agent memory should be true",
            )

        if clean_skill:
            await AgentSkillData.clean_data(agent_id)
            await ChatSkillData.clean_data(agent_id, chat_id)

        async with get_session() as db:
            if clean_agent:
                chat_id = chat_id.strip()
                q_suffix = "%"
                if chat_id and chat_id != "":
                    q_suffix = chat_id

                deletion_param = {"value": agent_id + "-" + q_suffix}
                await db.execute(
                    sqlalchemy.text(
                        "DELETE FROM checkpoints WHERE thread_id like :value",
                    ),
                    deletion_param,
                )
                await db.execute(
                    sqlalchemy.text(
                        "DELETE FROM checkpoint_writes WHERE thread_id like :value",
                    ),
                    deletion_param,
                )
                await db.execute(
                    sqlalchemy.text(
                        "DELETE FROM checkpoint_blobs WHERE thread_id like :value",
                    ),
                    deletion_param,
                )

            # update the updated_at field so that the agent instance will all reload
            await db.execute(
                update(AgentTable)
                .where(AgentTable.id == agent_id)
                .values(updated_at=func.now())
            )
            await db.commit()

        logger.info(f"Agent [{agent_id}] data cleaned up successfully.")
        return "Agent data cleaned up successfully."
    except SQLAlchemyError as e:
        # Handle other SQLAlchemy-related errors
        logger.error(e)
        raise IntentKitAPIError(status_code=500, key="DatabaseError", message=str(e))
    except Exception as e:
        logger.error("failed to cleanup the agent memory: " + str(e))
        raise e


async def thread_stats(agent_id: str, chat_id: str) -> list[BaseMessage]:
    thread_id = f"{agent_id}-{chat_id}"
    stream_config = {"configurable": {"thread_id": thread_id}}
    executor, _ = await agent_executor(agent_id)
    snap = await executor.aget_state(stream_config)
    if snap.values and "messages" in snap.values:
        return snap.values["messages"]
    else:
        return []
