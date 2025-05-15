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
import textwrap
import time
import traceback
from datetime import datetime
from typing import Optional

import sqlalchemy
from coinbase_agentkit import (
    AgentKit,
    AgentKitConfig,
    CdpWalletProvider,
    CdpWalletProviderConfig,
    basename_action_provider,
    cdp_api_action_provider,
    cdp_wallet_action_provider,
    erc20_action_provider,
    morpho_action_provider,
    pyth_action_provider,
    superfluid_action_provider,
    wallet_action_provider,
    weth_action_provider,
    wow_action_provider,
)
from coinbase_agentkit.action_providers.erc721 import erc721_action_provider
from coinbase_agentkit_langchain import get_langchain_tools
from epyxid import XID
from fastapi import HTTPException
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.graph import CompiledGraph
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError

from abstracts.graph import AgentState
from app.config.config import config
from app.core.agent import AgentStore
from app.core.credit import expense_message, expense_skill, skill_cost
from app.core.graph import create_agent
from app.core.prompt import agent_prompt
from app.core.skill import skill_store
from models.agent import Agent, AgentData, AgentQuota, AgentTable
from models.app_setting import AppSetting
from models.chat import AuthorType, ChatMessage, ChatMessageCreate, ChatMessageSkillCall
from models.credit import CreditAccount, OwnerType
from models.db import get_pool, get_session
from models.llm import get_model_cost
from models.skill import AgentSkillData, Skill, ThreadSkillData
from skills.acolyt import get_acolyt_skill
from skills.allora import get_allora_skill
from skills.cdp.get_balance import GetBalance
from skills.elfa import get_elfa_skill
from skills.enso import get_enso_skill
from skills.goat import (
    create_smart_wallets_if_not_exist,
    get_goat_skill,
    init_smart_wallets,
)
from skills.twitter import get_twitter_skill

logger = logging.getLogger(__name__)


# Global variable to cache all agent executors
_agents: dict[str, CompiledGraph] = {}
_private_agents: dict[str, CompiledGraph] = {}

# Global dictionaries to cache agent update times
_agents_updated: dict[str, datetime] = {}
_private_agents_updated: dict[str, datetime] = {}


async def initialize_agent(aid, is_private=False):
    """Initialize an AI agent with specified configuration and tools.

    This function:
    1. Loads agent configuration from database
    2. Initializes LLM with specified model
    3. Loads and configures requested tools
    4. Sets up PostgreSQL-based memory
    5. Creates and caches the agent

    Args:
        aid (str): Agent ID to initialize
        is_private (bool, optional): Flag indicating whether the agent is private. Defaults to False.

    Returns:
        Agent: Initialized LangChain agent

    Raises:
        HTTPException: If agent not found (404) or database error (500)
    """
    """Initialize the agent with CDP Agentkit."""
    # init agent store
    agent_store = AgentStore(aid)

    # get the agent from the database
    agent: Optional[Agent] = await Agent.get(aid)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent_data: Optional[AgentData] = await AgentData.get(aid)

    # ==== Initialize LLM using the LLM abstraction.
    from models.llm import create_llm_model

    # Create the LLM model instance
    llm_model = create_llm_model(
        model_name=agent.model,
        temperature=agent.temperature,
        frequency_penalty=agent.frequency_penalty,
        presence_penalty=agent.presence_penalty,
    )

    # Get the LLM instance
    llm = await llm_model.create_instance(config)

    # Get the token limit from the model info
    input_token_limit = min(config.input_token_limit, await llm_model.get_token_limit())

    # ==== Store buffered conversation history in memory.
    memory = AsyncPostgresSaver(get_pool())

    # ==== Load skills
    tools: list[BaseTool] = []

    if agent.skills:
        for k, v in agent.skills.items():
            if not v.get("enabled", False):
                continue
            try:
                skill_module = importlib.import_module(f"skills.{k}")
                if hasattr(skill_module, "get_skills"):
                    skill_tools = await skill_module.get_skills(
                        v, is_private, skill_store, agent_id=aid
                    )
                    if skill_tools and len(skill_tools) > 0:
                        tools.extend(skill_tools)
                else:
                    logger.error(f"Skill {k} does not have get_skills function")
            except ImportError as e:
                logger.error(f"Could not import skill module: {k} ({e})")

    # Configure CDP Agentkit Langchain Extension.
    # Deprecated
    cdp_wallet_provider = None
    if (
        agent.cdp_enabled
        and agent_data
        and agent_data.cdp_wallet_data
        and agent.cdp_skills
        and ("cdp" not in agent.skills if agent.skills else True)
    ):
        cdp_wallet_provider_config = CdpWalletProviderConfig(
            api_key_name=config.cdp_api_key_name,
            api_key_private_key=config.cdp_api_key_private_key,
            network_id=agent.cdp_network_id,
            wallet_data=agent_data.cdp_wallet_data,
        )
        cdp_wallet_provider = CdpWalletProvider(cdp_wallet_provider_config)
        agent_kit = AgentKit(
            AgentKitConfig(
                wallet_provider=cdp_wallet_provider,
                action_providers=[
                    wallet_action_provider(),
                    cdp_api_action_provider(cdp_wallet_provider_config),
                    cdp_wallet_action_provider(cdp_wallet_provider_config),
                    pyth_action_provider(),
                    basename_action_provider(),
                    erc20_action_provider(),
                    erc721_action_provider(),
                    weth_action_provider(),
                    morpho_action_provider(),
                    superfluid_action_provider(),
                    wow_action_provider(),
                ],
            )
        )
        cdp_tools = get_langchain_tools(agent_kit)
        for skill in agent.cdp_skills:
            if skill == "get_balance":
                tools.append(
                    GetBalance(
                        wallet=cdp_wallet_provider._wallet,
                        agent_id=aid,
                        skill_store=skill_store,
                    )
                )
                continue
            for tool in cdp_tools:
                if tool.name.endswith(skill):
                    tools.append(tool)

    if (
        agent.goat_enabled
        and agent.crossmint_config
        and ("goat" not in agent.skills if agent.skills else True)
    ):
        if (
            hasattr(config, "chain_provider")
            and config.crossmint_api_key
            and config.crossmint_api_base_url
        ):
            crossmint_networks = agent.crossmint_config.get("networks")
            if crossmint_networks and len(crossmint_networks) > 0:
                crossmint_wallet_data = (
                    agent_data.crossmint_wallet_data
                    if agent_data.crossmint_wallet_data
                    else {}
                )
                try:
                    smart_wallet_data = create_smart_wallets_if_not_exist(
                        config.crossmint_api_base_url,
                        config.crossmint_api_key,
                        crossmint_wallet_data.get("smart"),
                    )

                    # save the wallet after first create
                    if (
                        not crossmint_wallet_data
                        or not crossmint_wallet_data.get("smart")
                        or not crossmint_wallet_data.get("smart").get("evm")
                        or not crossmint_wallet_data.get("smart")
                        .get("evm")
                        .get("address")
                    ):
                        await agent_store.set_data(
                            {
                                "crossmint_wallet_data": {"smart": smart_wallet_data},
                            }
                        )

                    # give rpc some time to prevent error #429
                    time.sleep(1)

                    evm_crossmint_wallets = init_smart_wallets(
                        config.crossmint_api_key,
                        config.chain_provider,
                        crossmint_networks,
                        smart_wallet_data["evm"],
                    )

                    for wallet in evm_crossmint_wallets:
                        try:
                            s = get_goat_skill(
                                wallet,
                                agent.goat_skills,
                                skill_store,
                                agent_store,
                                aid,
                            )
                            tools.extend(s)
                        except Exception as e:
                            logger.warning(e)
                except Exception as e:
                    logger.warning(e)

    # Enso skills
    if (
        agent.enso_skills
        and len(agent.enso_skills) > 0
        and agent.enso_config
        and ("enso" not in agent.skills if agent.skills else True)
    ):
        for skill in agent.enso_skills:
            try:
                s = get_enso_skill(
                    skill,
                    skill_store,
                )
                tools.append(s)
            except Exception as e:
                logger.warning(e)
    # Acoalyt skills
    if (
        agent.acolyt_skills
        and len(agent.acolyt_skills) > 0
        and ("acolyt" not in agent.skills if agent.skills else True)
    ):
        for skill in agent.acolyt_skills:
            try:
                s = get_acolyt_skill(
                    skill,
                    skill_store,
                )
                tools.append(s)
            except Exception as e:
                logger.warning(e)
    # Allora skills
    if (
        agent.allora_skills
        and len(agent.allora_skills) > 0
        and ("allora" not in agent.skills if agent.skills else True)
    ):
        for skill in agent.allora_skills:
            try:
                s = get_allora_skill(
                    skill,
                    skill_store,
                )
                tools.append(s)
            except Exception as e:
                logger.warning(e)
    # Elfa skills
    if (
        agent.elfa_skills
        and len(agent.elfa_skills) > 0
        and ("elfa" not in agent.skills if agent.skills else True)
    ):
        for skill in agent.elfa_skills:
            try:
                s = get_elfa_skill(
                    skill,
                    skill_store,
                )
                tools.append(s)
            except Exception as e:
                logger.warning(e)
    # Twitter skills
    if (
        agent.twitter_skills
        and len(agent.twitter_skills) > 0
        and ("twitter" not in agent.skills if agent.skills else True)
    ):
        for skill in agent.twitter_skills:
            s = get_twitter_skill(
                skill,
                skill_store,
            )
            tools.append(s)

    # filter the duplicate tools
    tools = list({tool.name: tool for tool in tools}.values())

    # finally, set up the system prompt
    prompt = agent_prompt(agent, agent_data)
    # Escape curly braces in the prompt
    escaped_prompt = prompt.replace("{", "{{").replace("}", "}}")
    prompt_array = [
        ("system", escaped_prompt),
        ("placeholder", "{entrypoint_prompt}"),
        ("placeholder", "{messages}"),
    ]
    if agent.prompt_append:
        # Escape any curly braces in prompt_append
        escaped_append = agent.prompt_append.replace("{", "{{").replace("}", "}}")
        if agent.model.startswith("deepseek"):
            prompt_array.insert(1, ("system", escaped_append))
        else:
            prompt_array.append(("system", escaped_append))

    prompt_temp = ChatPromptTemplate.from_messages(prompt_array)

    def formatted_prompt(
        state: AgentState, config: RunnableConfig
    ) -> list[BaseMessage]:
        # logger.debug(f"[{aid}] formatted prompt: {state}")
        entrypoint_prompt = []
        if config.get("configurable") and config["configurable"].get(
            "entrypoint_prompt"
        ):
            entrypoint_prompt = [
                ("system", config["configurable"]["entrypoint_prompt"])
            ]
        return prompt_temp.invoke(
            {"messages": state["messages"], "entrypoint_prompt": entrypoint_prompt},
            config,
        )

    # hack for deepseek r1, it doesn't support tools
    if agent.model in [
        "deepseek-reasoner",
    ]:
        tools = []

    # log all tools
    for tool in tools:
        logger.info(
            f"[{aid}{'-private' if is_private else ''}] loaded tool: {tool.name}"
        )
    logger.debug(
        f"[{aid}{'-private' if is_private else ''}] init prompt: {escaped_prompt}"
    )

    # Create ReAct Agent using the LLM and CDP Agentkit tools.
    executor = create_agent(
        aid,
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=formatted_prompt,
        debug=config.debug_checkpoint,
        input_token_limit=input_token_limit,
    )
    if is_private:
        _private_agents[aid] = executor
        _private_agents_updated[aid] = agent.updated_at
    else:
        _agents[aid] = executor
        _agents_updated[aid] = agent.updated_at


async def agent_executor(agent_id: str, is_private: bool) -> (CompiledGraph, float):
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


async def execute_agent(
    message: ChatMessageCreate, debug: bool = False
) -> list[ChatMessage]:
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
    start = time.perf_counter()
    # make sure reply_to is set
    message.reply_to = message.id
    input = await message.save()

    agent = await Agent.get(input.agent_id)

    need_payment = await is_payment_required(input, agent)

    # check user balance
    if need_payment:
        quota = await AgentQuota.get(message.agent_id)
        if quota and quota.free_income_daily > 24000:
            error_message_create = ChatMessageCreate(
                id=str(XID()),
                agent_id=input.agent_id,
                chat_id=input.chat_id,
                user_id=input.user_id,
                author_id=input.agent_id,
                author_type=AuthorType.SYSTEM,
                thread_type=input.author_type,
                reply_to=input.id,
                message="This Agent has reached its free CAP income limit for today! Start using paid CAPs or wait until this limit expires in less than 24 hours.",
                time_cost=time.perf_counter() - start,
            )
            error_message = await error_message_create.save()
            resp.append(error_message)
            return resp
        payer = input.user_id
        if (
            input.author_type == AuthorType.TELEGRAM
            or input.author_type == AuthorType.TWITTER
        ):
            payer = agent.owner
        user_account = await CreditAccount.get_or_create(OwnerType.USER, payer)
        if not user_account.has_sufficient_credits(1):
            error_message_create = ChatMessageCreate(
                id=str(XID()),
                agent_id=input.agent_id,
                chat_id=input.chat_id,
                user_id=input.user_id,
                author_id=input.agent_id,
                author_type=AuthorType.SYSTEM,
                thread_type=input.author_type,
                reply_to=input.id,
                message="Insufficient balance.",
                time_cost=time.perf_counter() - start,
            )
            error_message = await error_message_create.save()
            resp.append(error_message)
            return resp
        # use this in loop
        total_paid = 0

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

    # message
    # if the model doesn't natively support image parsing, add the image URLs to the message
    if agent.has_image_parser_skill() and image_urls:
        input.message += f"\n\nImages:\n{'\n'.join(image_urls)}"
    content = [
        {"type": "text", "text": input.message},
    ]
    if not agent.has_image_parser_skill() and image_urls:
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

    entrypoint_prompt = None
    if (
        agent.twitter_entrypoint_enabled
        and agent.twitter_entrypoint_prompt
        and input.author_type == AuthorType.TWITTER
    ):
        entrypoint_prompt = agent.twitter_entrypoint_prompt
        logger.debug("twitter entrypoint prompt added")
    elif (
        agent.telegram_entrypoint_enabled
        and agent.telegram_entrypoint_prompt
        and input.author_type == AuthorType.TELEGRAM
    ):
        entrypoint_prompt = agent.telegram_entrypoint_prompt
        logger.debug("telegram entrypoint prompt added")

    # stream config
    thread_id = f"{input.agent_id}-{input.chat_id}"
    stream_config = {
        "configurable": {
            "agent": agent,
            "thread_id": thread_id,
            "user_id": input.user_id,
            "entrypoint": input.author_type,
            "entrypoint_prompt": entrypoint_prompt,
        }
    }

    # run
    cached_tool_step = None
    async for chunk in executor.astream({"messages": messages}, stream_config):
        try:
            this_time = time.perf_counter()
            # logger.debug(f"stream chunk: {chunk}", extra={"thread_id": thread_id})
            if "agent" in chunk and "messages" in chunk["agent"]:
                if len(chunk["agent"]["messages"]) != 1:
                    logger.error(
                        "unexpected agent message: " + str(chunk["agent"]["messages"]),
                        extra={"thread_id": thread_id},
                    )
                msg = chunk["agent"]["messages"][0]
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    # tool calls, save for later use
                    cached_tool_step = msg
                    if need_payment:
                        for tool_call in msg.tool_calls:
                            skill_meta = await Skill.get(tool_call.get("name"))
                            if skill_meta:
                                skill_cost_info = await skill_cost(
                                    skill_meta.name, input.user_id, agent
                                )
                                total_paid += skill_cost_info.total_amount
                        if not user_account.has_sufficient_credits(total_paid):
                            error_message_create = ChatMessageCreate(
                                id=str(XID()),
                                agent_id=input.agent_id,
                                chat_id=input.chat_id,
                                user_id=input.user_id,
                                author_id=input.agent_id,
                                author_type=AuthorType.SYSTEM,
                                thread_type=input.author_type,
                                reply_to=input.id,
                                message="Insufficient balance.",
                                time_cost=this_time - last,
                            )
                            error_message = await error_message_create.save()
                            resp.append(error_message)
                            return resp
                elif hasattr(msg, "content") and msg.content:
                    # agent message
                    chat_message_create = ChatMessageCreate(
                        id=str(XID()),
                        agent_id=input.agent_id,
                        chat_id=input.chat_id,
                        user_id=input.user_id,
                        author_id=input.agent_id,
                        author_type=AuthorType.AGENT,
                        thread_type=input.author_type,
                        reply_to=input.id,
                        message=msg.content,
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
                        if need_payment:
                            amount = await get_model_cost(
                                agent.model,
                                chat_message_create.input_tokens,
                                chat_message_create.output_tokens,
                            )
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
                        resp.append(chat_message)
                else:
                    logger.error(
                        "unexpected agent message: " + str(msg),
                        extra={"thread_id": thread_id},
                    )
            elif "tools" in chunk and "messages" in chunk["tools"]:
                if not cached_tool_step:
                    logger.error(
                        "unexpected tools message: " + str(chunk["tools"]),
                        extra={"thread_id": thread_id},
                    )
                    continue
                skill_calls = []
                for msg in chunk["tools"]["messages"]:
                    if not hasattr(msg, "tool_call_id"):
                        logger.error(
                            "unexpected tools message: " + str(chunk["tools"]),
                            extra={"thread_id": thread_id},
                        )
                        continue
                    for call in cached_tool_step.tool_calls:
                        if call["id"] == msg.tool_call_id:
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
                            skill_calls.append(skill_call)
                            break
                skill_message_create = ChatMessageCreate(
                    id=str(XID()),
                    agent_id=input.agent_id,
                    chat_id=input.chat_id,
                    user_id=input.user_id,
                    author_id=input.agent_id,
                    author_type=AuthorType.SKILL,
                    thread_type=input.author_type,
                    reply_to=input.id,
                    message="",
                    skill_calls=skill_calls,
                    input_tokens=(
                        cached_tool_step.usage_metadata.get("input_tokens", 0)
                        if hasattr(cached_tool_step, "usage_metadata")
                        and cached_tool_step.usage_metadata
                        else 0
                    ),
                    output_tokens=(
                        cached_tool_step.usage_metadata.get("output_tokens", 0)
                        if hasattr(cached_tool_step, "usage_metadata")
                        and cached_tool_step.usage_metadata
                        else 0
                    ),
                    time_cost=this_time - last,
                )
                last = this_time
                if cold_start_cost > 0:
                    skill_message_create.cold_start_cost = cold_start_cost
                    cold_start_cost = 0
                cached_tool_step = None
                # save message and credit in one transaction
                async with get_session() as session:
                    if need_payment:
                        # message payment
                        message_amount = await get_model_cost(
                            agent.model,
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
                        skill_message_create.credit_event_id = message_payment_event.id
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
                    resp.append(skill_message)
            elif "memory_manager" in chunk:
                pass
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
            error_message_create = ChatMessageCreate(
                id=str(XID()),
                agent_id=input.agent_id,
                chat_id=input.chat_id,
                user_id=input.user_id,
                author_id=input.agent_id,
                author_type=AuthorType.SYSTEM,
                thread_type=input.author_type,
                reply_to=input.id,
                message="IntentKit internal error",
                time_cost=time.perf_counter() - start,
            )
            error_message = await error_message_create.save()
            resp.append(error_message)
            return resp
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(
                f"failed to execute agent: {str(e)}\n{error_traceback}",
                extra={"thread_id": thread_id},
            )
            error_message_create = ChatMessageCreate(
                id=str(XID()),
                agent_id=input.agent_id,
                chat_id=input.chat_id,
                user_id=input.user_id,
                author_id=input.agent_id,
                author_type=AuthorType.SYSTEM,
                thread_type=input.author_type,
                reply_to=input.id,
                message=f"Error in agent:\n  {str(e)}",
                time_cost=time.perf_counter() - start,
            )
            error_message = await error_message_create.save()
            resp.append(error_message)
            return resp
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


async def is_payment_required(input: ChatMessageCreate, agent: Agent) -> bool:
    if not config.payment_enabled:
        return False
    payment_settings = await AppSetting.payment()
    if payment_settings.agent_whitelist_enabled:
        if agent.id not in payment_settings.agent_whitelist:
            return False
    if input.user_id and agent.owner:
        return True
    return False
