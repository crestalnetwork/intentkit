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
from typing import Optional

import sqlalchemy
from epyxid import XID
from fastapi import HTTPException
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
)
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError

from intentkit.abstracts.graph import AgentContext, AgentError, AgentState
from intentkit.config.config import config
from intentkit.core.credit import expense_message, expense_skill
from intentkit.core.node import PreModelNode, post_model_node
from intentkit.core.prompt import (
    create_formatted_prompt_function,
    explain_prompt,
)
from intentkit.core.skill import skill_store
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
from intentkit.models.db import get_langgraph_checkpointer, get_session
from intentkit.models.llm import LLMModelInfo, LLMProvider
from intentkit.models.skill import AgentSkillData, ThreadSkillData
from intentkit.models.user import User
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


# Global variable to cache all agent executors
_agents: dict[str, CompiledStateGraph] = {}
_private_agents: dict[str, CompiledStateGraph] = {}

# Global dictionaries to cache agent update times
_agents_updated: dict[str, datetime] = {}
_private_agents_updated: dict[str, datetime] = {}


async def create_agent(
    agent: Agent, is_private: bool = False, has_search: bool = False
) -> CompiledStateGraph:
    """Create an AI agent with specified configuration and tools.

    This function:
    1. Initializes LLM with specified model
    2. Loads and configures requested tools
    3. Sets up PostgreSQL-based memory
    4. Creates and returns the agent

    Args:
        agent (Agent): Agent configuration object
        is_private (bool, optional): Flag indicating whether the agent is private. Defaults to False.
        has_search (bool, optional): Flag indicating whether to include search tools. Defaults to False.

    Returns:
        CompiledStateGraph: Initialized LangChain agent
    """
    agent_data = await AgentData.get(agent.id)

    # ==== Initialize LLM using the LLM abstraction.
    from intentkit.models.llm import create_llm_model

    # Create the LLM model instance
    llm_model = await create_llm_model(
        model_name=agent.model,
        temperature=agent.temperature,
        frequency_penalty=agent.frequency_penalty,
        presence_penalty=agent.presence_penalty,
    )

    # Get the LLM instance
    llm = await llm_model.create_instance(config)

    # Get the token limit from the model info
    input_token_limit = min(config.input_token_limit, llm_model.info.context_length)

    # ==== Store buffered conversation history in memory.
    memory = get_langgraph_checkpointer()

    # ==== Load skills
    tools: list[BaseTool | dict] = []

    if agent.skills:
        for k, v in agent.skills.items():
            if not v.get("enabled", False):
                continue
            try:
                skill_module = importlib.import_module(f"intentkit.skills.{k}")
                if hasattr(skill_module, "get_skills"):
                    skill_tools = await skill_module.get_skills(
                        v, is_private, skill_store, agent_id=agent.id
                    )
                    if skill_tools and len(skill_tools) > 0:
                        tools.extend(skill_tools)
                else:
                    logger.error(f"Skill {k} does not have get_skills function")
            except ImportError as e:
                logger.error(f"Could not import skill module: {k} ({e})")

    # filter the duplicate tools
    tools = list({tool.name: tool for tool in tools}.values())

    # Add search tools if requested
    if (
        has_search
        and llm_model.info.provider == LLMProvider.OPENAI
        and llm_model.info.supports_search
        and not agent.model.startswith(
            "gpt-5"
        )  # tmp disable gpt-5 search since package bugs
    ):
        tools.append({"type": "web_search_preview"})

    # Create the formatted_prompt function using the refactored prompt module
    formatted_prompt = create_formatted_prompt_function(agent, agent_data)

    for tool in tools:
        logger.info(
            f"[{agent.id}{'-private' if is_private else ''}] loaded tool: {tool.name if isinstance(tool, BaseTool) else tool}"
        )

    # Pre model hook
    pre_model_hook = PreModelNode(
        model=llm,
        short_term_memory_strategy=agent.short_term_memory_strategy,
        max_tokens=input_token_limit // 2,
        max_summary_tokens=2048,  # later we can let agent to set this
    )

    # Create ReAct Agent using the LLM and CDP Agentkit tools.
    executor = create_react_agent(
        model=llm,
        tools=tools,
        prompt=formatted_prompt,
        pre_model_hook=pre_model_hook,
        post_model_hook=post_model_node if config.payment_enabled else None,
        state_schema=AgentState,
        context_schema=AgentContext,
        checkpointer=memory,
        debug=config.debug_checkpoint,
        name=agent.id,
    )

    return executor


async def initialize_agent(aid, is_private=False):
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
    agent: Optional[Agent] = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Determine if search should be enabled based on model capabilities
    from intentkit.models.llm import create_llm_model

    llm_model = await create_llm_model(
        model_name=agent.model,
        temperature=agent.temperature,
        frequency_penalty=agent.frequency_penalty,
        presence_penalty=agent.presence_penalty,
    )
    has_search = (
        llm_model.info.provider == LLMProvider.OPENAI and llm_model.info.supports_search
    )

    # Create the agent using the new create_agent function
    executor = await create_agent(agent, is_private, has_search)

    # Cache the agent executor
    if is_private:
        _private_agents[aid] = executor
        _private_agents_updated[aid] = agent.updated_at
    else:
        _agents[aid] = executor
        _agents_updated[aid] = agent.updated_at


async def agent_executor(
    agent_id: str, is_private: bool
) -> (CompiledStateGraph, float):
    start = time.perf_counter()
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agents = _private_agents if is_private else _agents
    agents_updated = _private_agents_updated if is_private else _agents_updated

    # Check if agent needs reinitialization due to updates
    needs_reinit = False
    if agent_id in agents:
        if (
            agent_id not in agents_updated
            or agent.updated_at != agents_updated[agent_id]
        ):
            needs_reinit = True
            logger.info(
                f"Reinitializing agent {agent_id} due to updates, private mode: {is_private}"
            )

    # cold start or needs reinitialization
    cold_start_cost = 0.0
    if (agent_id not in agents) or needs_reinit:
        await initialize_agent(agent_id, is_private)
        cold_start_cost = time.perf_counter() - start
    return agents[agent_id], cold_start_cost


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
    start = time.perf_counter()
    # make sure reply_to is set
    message.reply_to = message.id

    # save input message first
    input = await message.save()

    # agent
    agent = await Agent.get(input.agent_id)

    # model
    model = await LLMModelInfo.get(agent.model)

    payment_enabled = config.payment_enabled

    # check user balance
    if payment_enabled:
        if not input.user_id or not agent.owner:
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
                    agent_id=input.agent_id,
                    chat_id=input.chat_id,
                    user_id=input.user_id,
                    author_id=input.agent_id,
                    thread_type=input.author_type,
                    reply_to=input.id,
                    time_cost=time.perf_counter() - start,
                )
                error_message = await error_message_create.save()
                yield error_message
                return
        # payer
        payer = input.user_id
        if input.author_type in [
            AuthorType.TELEGRAM,
            AuthorType.TWITTER,
            AuthorType.API,
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
                    agent_id=input.agent_id,
                    chat_id=input.chat_id,
                    user_id=input.user_id,
                    author_id=input.agent_id,
                    thread_type=input.author_type,
                    reply_to=input.id,
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
                agent_id=input.agent_id,
                chat_id=input.chat_id,
                user_id=input.user_id,
                author_id=input.agent_id,
                thread_type=input.author_type,
                reply_to=input.id,
                time_cost=time.perf_counter() - start,
            )
            error_message = await error_message_create.save()
            yield error_message
            return

    is_private = False
    if input.user_id == agent.owner:
        is_private = True

    executor, cold_start_cost = await agent_executor(input.agent_id, is_private)
    last = start + cold_start_cost

    # Extract images from attachments
    image_urls = []
    if input.attachments:
        image_urls = [
            att["url"]
            for att in input.attachments
            if "type" in att and att["type"] == "image" and "url" in att
        ]

    # Process input message to handle @skill patterns
    if config.admin_llm_skill_control:
        input_message = await explain_prompt(input.message)
    else:
        input_message = input.message

    # super mode
    recursion_limit = 30
    if re.search(r"\b@super\b", input_message):
        recursion_limit = 300
        # Remove @super from the message
        input_message = re.sub(r"\b@super\b", "", input_message).strip()

    # llm native search
    if re.search(r"\b@search\b", input_message) or re.search(
        r"\b@web\b", input_message
    ):
        if model.supports_search:
            input_message = re.sub(
                r"\b@search\b",
                "(You have native search tool, you can use it to get more recent information)",
                input_message,
            ).strip()
            input_message = re.sub(
                r"\b@web\b",
                "(You have native search tool, you can use it to get more recent information)",
                input_message,
            ).strip()
        else:
            input_message = re.sub(r"\b@search\b", "", input_message).strip()
            input_message = re.sub(r"\b@web\b", "", input_message).strip()

    # content to llm
    content = [
        {"type": "text", "text": input_message},
    ]
    # if the model doesn't natively support image parsing, add the image URLs to the message
    if image_urls:
        if (
            agent.has_image_parser_skill(is_private=is_private)
            and not model.supports_image_input
        ):
            input_message += f"\n\nImages:\n{'\n'.join(image_urls)}"
            content = [
                {"type": "text", "text": input_message},
            ]
        else:
            # anyway, pass it directly to LLM
            content.extend(
                [
                    {"type": "image_url", "image_url": {"url": image_url}}
                    for image_url in image_urls
                ]
            )

    messages = [
        HumanMessage(content=content),
    ]

    # stream config
    thread_id = f"{input.agent_id}-{input.chat_id}"
    stream_config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": recursion_limit,
    }

    context = AgentContext(
        agent_id=input.agent_id,
        chat_id=input.chat_id,
        user_id=input.user_id,
        app_id=input.app_id,
        entrypoint=input.author_type,
        is_private=is_private,
        payer=payer if payment_enabled else None,
    )

    # run
    cached_tool_step = None
    try:
        async for chunk in executor.astream(
            {"messages": messages}, context=context, config=stream_config
        ):
            this_time = time.perf_counter()
            logger.debug(f"stream chunk: {chunk}", extra={"thread_id": thread_id})
            if "agent" in chunk and "messages" in chunk["agent"]:
                if len(chunk["agent"]["messages"]) != 1:
                    logger.error(
                        "unexpected agent message: " + str(chunk["agent"]["messages"]),
                        extra={"thread_id": thread_id},
                    )
                msg = chunk["agent"]["messages"][0]
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    # tool calls, save for later use, if it is deleted by post_model_hook, will not be used.
                    cached_tool_step = msg
                if hasattr(msg, "content") and msg.content:
                    content = msg.content
                    if isinstance(msg.content, list):
                        # in new version, content item maybe a list
                        content = msg.content[0]
                    if isinstance(content, dict):
                        if "text" in content:
                            content = content["text"]
                        else:
                            content = str(content)
                            logger.error(f"unexpected content type: {content}")
                    # agent message
                    chat_message_create = ChatMessageCreate(
                        id=str(XID()),
                        agent_id=input.agent_id,
                        chat_id=input.chat_id,
                        user_id=input.user_id,
                        author_id=input.agent_id,
                        author_type=AuthorType.AGENT,
                        model=agent.model,
                        thread_type=input.author_type,
                        reply_to=input.id,
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
                    if cold_start_cost > 0:
                        chat_message_create.cold_start_cost = cold_start_cost
                        cold_start_cost = 0
                    # handle message and payment in one transaction
                    async with get_session() as session:
                        # payment
                        if payment_enabled:
                            amount = await model.calculate_cost(
                                chat_message_create.input_tokens,
                                chat_message_create.output_tokens,
                            )

                            # Check for web_search_call in additional_kwargs
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
                                            f"[{input.agent_id}] Found web_search_call in additional_kwargs"
                                        )
                                        amount += 35
                                        break
                            credit_event = await expense_message(
                                session,
                                payer,
                                chat_message_create.id,
                                input.id,
                                amount,
                                agent,
                            )
                            logger.info(f"[{input.agent_id}] expense message: {amount}")
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
                            if msg.status == "error":
                                skill_call["success"] = False
                                skill_call["error_message"] = str(msg.content)
                            else:
                                if config.debug:
                                    skill_call["response"] = str(msg.content)
                                else:
                                    skill_call["response"] = textwrap.shorten(
                                        str(msg.content), width=1000, placeholder="..."
                                    )
                                if msg.artifact:
                                    cached_attachments.extend(msg.artifact)
                            skill_calls.append(skill_call)
                            break
                skill_message_create = ChatMessageCreate(
                    id=str(XID()),
                    agent_id=input.agent_id,
                    chat_id=input.chat_id,
                    user_id=input.user_id,
                    author_id=input.agent_id,
                    author_type=AuthorType.SKILL,
                    model=agent.model,
                    thread_type=input.author_type,
                    reply_to=input.id,
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
                if cold_start_cost > 0:
                    skill_message_create.cold_start_cost = cold_start_cost
                    cold_start_cost = 0
                # save message and credit in one transaction
                async with get_session() as session:
                    if payment_enabled:
                        # message payment, only first call in a group has message bill
                        if have_first_call_in_cache:
                            message_amount = await model.calculate_cost(
                                skill_message_create.input_tokens,
                                skill_message_create.output_tokens,
                            )
                            message_payment_event = await expense_message(
                                session,
                                payer,
                                skill_message_create.id,
                                input.id,
                                message_amount,
                                agent,
                            )
                            skill_message_create.credit_event_id = (
                                message_payment_event.id
                            )
                            skill_message_create.credit_cost = (
                                message_payment_event.total_amount
                            )
                        # skill payment
                        for skill_call in skill_calls:
                            if not skill_call["success"]:
                                continue
                            payment_event = await expense_skill(
                                session,
                                payer,
                                skill_message_create.id,
                                input.id,
                                skill_call["id"],
                                skill_call["name"],
                                agent,
                            )
                            skill_call["credit_event_id"] = payment_event.id
                            skill_call["credit_cost"] = payment_event.total_amount
                            logger.info(
                                f"[{input.agent_id}] skill payment: {skill_call}"
                            )
                    skill_message_create.skill_calls = skill_calls
                    skill_message = await skill_message_create.save_in_session(session)
                    await session.commit()
                    yield skill_message
            elif "pre_model_hook" in chunk:
                pass
            elif "post_model_hook" in chunk:
                logger.debug(
                    f"post_model_hook: {chunk}",
                    extra={"thread_id": thread_id},
                )
                if chunk["post_model_hook"] and "error" in chunk["post_model_hook"]:
                    if (
                        chunk["post_model_hook"]["error"]
                        == AgentError.INSUFFICIENT_CREDITS
                    ):
                        if "messages" in chunk["post_model_hook"]:
                            msg = chunk["post_model_hook"]["messages"][-1]
                            content = msg.content
                            if isinstance(msg.content, list):
                                # in new version, content item maybe a list
                                content = msg.content[0]
                            post_model_message_create = ChatMessageCreate(
                                id=str(XID()),
                                agent_id=input.agent_id,
                                chat_id=input.chat_id,
                                user_id=input.user_id,
                                author_id=input.agent_id,
                                author_type=AuthorType.AGENT,
                                model=agent.model,
                                thread_type=input.author_type,
                                reply_to=input.id,
                                message=content,
                                input_tokens=0,
                                output_tokens=0,
                                time_cost=this_time - last,
                            )
                            last = this_time
                            if cold_start_cost > 0:
                                post_model_message_create.cold_start_cost = (
                                    cold_start_cost
                                )
                                cold_start_cost = 0
                            post_model_message = await post_model_message_create.save()
                            yield post_model_message
                        error_message_create = (
                            await ChatMessageCreate.from_system_message(
                                SystemMessageType.INSUFFICIENT_BALANCE,
                                agent_id=input.agent_id,
                                chat_id=input.chat_id,
                                user_id=input.user_id,
                                author_id=input.agent_id,
                                thread_type=input.author_type,
                                reply_to=input.id,
                                time_cost=0,
                            )
                        )
                        error_message = await error_message_create.save()
                        yield error_message
            else:
                error_traceback = traceback.format_exc()
                logger.error(
                    f"unexpected message type: {str(chunk)}\n{error_traceback}",
                    extra={"thread_id": thread_id},
                )
    except SQLAlchemyError as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id},
        )
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            agent_id=input.agent_id,
            chat_id=input.chat_id,
            user_id=input.user_id,
            author_id=input.agent_id,
            thread_type=input.author_type,
            reply_to=input.id,
            time_cost=time.perf_counter() - start,
        )
        error_message = await error_message_create.save()
        yield error_message
        return
    except GraphRecursionError as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"reached recursion limit: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id, "agent_id": input.agent_id},
        )
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.STEP_LIMIT_EXCEEDED,
            agent_id=input.agent_id,
            chat_id=input.chat_id,
            user_id=input.user_id,
            author_id=input.agent_id,
            thread_type=input.author_type,
            reply_to=input.id,
            time_cost=time.perf_counter() - start,
        )
        error_message = await error_message_create.save()
        yield error_message
        return
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"failed to execute agent: {str(e)}\n{error_traceback}",
            extra={"thread_id": thread_id, "agent_id": input.agent_id},
        )
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.AGENT_INTERNAL_ERROR,
            agent_id=input.agent_id,
            chat_id=input.chat_id,
            user_id=input.user_id,
            author_id=input.agent_id,
            thread_type=input.author_type,
            reply_to=input.id,
            time_cost=time.perf_counter() - start,
        )
        error_message = await error_message_create.save()
        yield error_message
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
            raise HTTPException(
                status_code=400,
                detail="at least one of skills data or agent memory should be true.",
            )

        if clean_skill:
            await AgentSkillData.clean_data(agent_id)
            await ThreadSkillData.clean_data(agent_id, chat_id)

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
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("failed to cleanup the agent memory: " + str(e))
        raise e


async def thread_stats(agent_id: str, chat_id: str) -> list[BaseMessage]:
    thread_id = f"{agent_id}-{chat_id}"
    stream_config = {"configurable": {"thread_id": thread_id}}
    is_private = False
    if chat_id.startswith("owner") or chat_id.startswith("autonomous"):
        is_private = True
    executor, _ = await agent_executor(agent_id, is_private)
    snap = await executor.aget_state(stream_config)
    if snap.values and "messages" in snap.values:
        return snap.values["messages"]
    else:
        return []
