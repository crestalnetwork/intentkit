"""AI Agent Management Module.

This module provides functionality for initializing and executing AI agents. It handles:
- Agent initialization with LangChain
- Tool and skill management
- Agent execution and response handling
- Memory management with PostgreSQL
- Integration with CDP and Twitter

The module uses a global cache to store initialized agents for better performance.
"""

import logging
import time

from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from fastapi import HTTPException
from langchain_core.messages import (
    HumanMessage,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.graph import CompiledGraph
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from sqlmodel import select

from abstracts.engine import AgentMessageInput
from abstracts.graph import AgentState
from app.config.config import config
from app.core.agent import AgentStore
from app.core.graph import create_agent
from app.core.skill import SkillStore
from app.services.twitter.client import TwitterClient
from app.services.twitter.oauth2 import get_authorization_url
from models.agent import Agent, AgentData
from models.db import get_coon, get_session
from skill_sets import get_skill_set
from skills.common import get_common_skill
from skills.crestal import get_crestal_skill
from skills.enso import get_enso_skill
from skills.twitter import get_twitter_skill

logger = logging.getLogger(__name__)

# Global variable to cache all agent executors
agents: dict[str, CompiledGraph] = {}


def agent_prompt(agent: Agent) -> str:
    prompt = ""
    if config.system_prompt:
        prompt += config.system_prompt + "\n\n"
    if agent.name:
        prompt += f"Your name is {agent.name}.\n\n"
    if agent.prompt:
        prompt += agent.prompt
    elif agent.cdp_enabled:
        prompt += (
            "You are a helpful agent that can interact onchain using the Coinbase Developer Platform AgentKit. "
            "You are empowered to interact onchain using your tools. If you ever need funds, you can request "
            "them from the faucet if you are on network ID 'base-sepolia'. If not, you can provide your wallet "
            "details and request funds from the user. Before executing your first action, get the wallet details "
            "to see what network you're on. If there is a 5XX (internal) HTTP error code, ask the user to try "
            "again later. If someone asks you to do something you can't do with your currently available tools, "
            "you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, "
            "recommend they go to docs.cdp.coinbase.com for more information. Be concise and helpful with your "
            "responses. Refrain from restating your tools' descriptions unless it is explicitly requested."
        )
    if agent.cdp_enabled:
        prompt += """\n\nWallet addresses are public information.  If someone asks for your default wallet, 
            current wallet, personal wallet, crypto wallet, or wallet public address, don't use any address in message history,
            you must use the "get_wallet_details" tool to retrieve your wallet address every time.\n\n"""
    if agent.enso_enabled:
        prompt += """\n\nYou are integrated to Enso API, you are able to get the token list and their information, such
        as APY, Protocol Slug, Symbol, Address, and underlying tokens using enso_get_tokens tool. for each thread first
        request, you should use enso_get_tokens with no input param and get the information of the available protocol slugs, 
        symbols, addresses and APY. For token deposit, swap and route shortcut, you should use get_route tool. to get wallet balances 
        use get_wallet_balances. to get wallet approvals use get_wallet_approvals.\n\n"""
    return prompt


def initialize_agent(aid):
    """Initialize an AI agent with specified configuration and tools.

    This function:
    1. Loads agent configuration from database
    2. Initializes LLM with specified model
    3. Loads and configures requested tools
    4. Sets up PostgreSQL-based memory
    5. Creates and caches the agent

    Args:
        aid (str): Agent ID to initialize

    Returns:
        Agent: Initialized LangChain agent

    Raises:
        HTTPException: If agent not found (404) or database error (500)
    """
    """Initialize the agent with CDP Agentkit."""
    # init skill store first
    skill_store = SkillStore(get_session)
    # init agent store
    agent_store = AgentStore(aid, get_session)

    # get the agent from the database
    try:
        agent: Agent = agent_store.get_config()
    except NoResultFound:
        # Handle the case where the user is not found
        raise HTTPException(status_code=404, detail="Agent not found")
    except SQLAlchemyError as e:
        # Handle other SQLAlchemy-related errors
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))

    # ==== Initialize LLM.
    llm = ChatOpenAI(model_name=agent.model, openai_api_key=config.openai_api_key)

    # ==== Store buffered conversation history in memory.
    memory = PostgresSaver(get_coon())

    # ==== Load skills
    tools: list[BaseTool] = []

    # Configure CDP Agentkit Langchain Extension.
    agent_data: AgentData = agent_store.get_data()
    if agent.cdp_enabled:
        values = {
            "cdp_api_key_name": config.cdp_api_key_name,
            "cdp_api_key_private_key": config.cdp_api_key_private_key,
            "network_id": getattr(agent, "cdp_network_id", "base-sepolia"),
        }
        if agent_data and agent_data.cdp_wallet_data:
            values["cdp_wallet_data"] = agent_data.cdp_wallet_data
        elif agent.cdp_wallet_data:
            # If there is a persisted agentic wallet, load it and pass to the CDP Agentkit Wrapper.
            values["cdp_wallet_data"] = agent.cdp_wallet_data
        agentkit = CdpAgentkitWrapper(**values)
        # save the wallet after first create
        if not agent_data or not agent_data.cdp_wallet_data:
            agent_store.set_data(
                {
                    "cdp_wallet_data": agentkit.export_wallet(),
                }
            )
        # Initialize CDP Agentkit Toolkit and get tools.
        cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
        cdp_tools = cdp_toolkit.get_tools()
        # Filter the tools to only include the ones that in agent.cdp_skills.
        if agent.cdp_skills and len(agent.cdp_skills) > 0:
            cdp_tools = [tool for tool in cdp_tools if tool.name in agent.cdp_skills]
        tools.extend(cdp_tools)

    # Enso skills
    if agent.enso_skills and len(agent.enso_skills) > 0 and agent.enso_config:
        for skill in agent.enso_skills:
            try:
                s = get_enso_skill(
                    skill,
                    agent.enso_config.get("api_token"),
                    agent.enso_config.get("main_tokens", list[str]()),
                    # TODO: replace it with CDP wallet.
                    agent.enso_config.get("from_address"),
                    skill_store,
                    aid,
                )
                tools.append(s)
            except Exception as e:
                logger.warning(e)
    # Twitter skills
    twitter_prompt = ""
    if agent.twitter_skills and len(agent.twitter_skills) > 0:
        if not agent.twitter_config:
            agent.twitter_config = {}
        try:
            twitter_client = TwitterClient(agent_store, agent.twitter_config)
            if not twitter_client.need_auth:
                for skill in agent.twitter_skills:
                    try:
                        s = get_twitter_skill(
                            skill,
                            twitter_client,
                            skill_store,
                            aid,
                            agent_store,
                        )
                        tools.append(s)
                    except Exception as e:
                        logger.warning(
                            f"Failed to initialize Twitter skill {skill}: {e}"
                        )
                twitter_prompt = (
                    f"\n\nYour twitter id is {agent_data.twitter_id}, never reply or retweet yourself. "
                    f"Your twitter username is {agent_data.twitter_username}. \n"
                    f"Your twitter name is {agent_data.twitter_name}. \n"
                )
            else:
                logger.info(f"Twitter client needs authentication for agent {aid}")
                twitter_prompt = (
                    "\n\nWhen you need to use any twitter tool, "
                    f"tell the person helping you to authenticate the Twitter account using this link: {get_authorization_url(aid)} \n"
                    "Remember, the link will be expired. So you can only use this one, not use other links in the conversation history.\n"
                    "Display links on separate lines, with a blank line before and after, not use markdown.\n\n"
                )
        except Exception as e:
            logger.warning(f"Failed to initialize Twitter client for agent {aid}: {e}")

    # Crestal skills
    if agent.crestal_skills:
        for skill in agent.crestal_skills:
            tools.append(get_crestal_skill(skill))

    # Common skills
    if agent.common_skills:
        for skill in agent.common_skills:
            tools.append(get_common_skill(skill))

    # Skill sets
    if agent.skill_sets:
        for skill_set, opts in agent.skill_sets.items():
            tools.extend(get_skill_set(skill_set, opts))

    # filter the duplicate tools
    tools = list({tool.name: tool for tool in tools}.values())

    # log all tools
    for tool in tools:
        logger.info(f"[{aid}] loaded tool: {tool.name}")

    # finally, setup the system prompt
    prompt = agent_prompt(agent)
    # Escape curly braces in the prompt
    escaped_prompt = prompt.replace("{", "{{").replace("}", "}}")
    prompt_array = [
        ("system", escaped_prompt),
        ("placeholder", "{messages}"),
    ]
    if twitter_prompt:
        prompt_array.append(("system", twitter_prompt))
    if agent.prompt_append:
        # Escape any curly braces in prompt_append
        escaped_append = agent.prompt_append.replace("{", "{{").replace("}", "}}")
        prompt_array.append(("system", escaped_append))
    prompt_temp = ChatPromptTemplate.from_messages(prompt_array)

    def formatted_prompt(state: AgentState):
        # logger.debug(f"[{aid}] formatted prompt: {state}")
        return prompt_temp.invoke({"messages": state["messages"]})

    # Create ReAct Agent using the LLM and CDP Agentkit tools.
    agents[aid] = create_agent(
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=formatted_prompt,
        debug=config.debug_checkpoint,
    )


def execute_agent(
        aid: str, message: AgentMessageInput, thread_id: str, debug: bool = False
) -> list[str]:
    """Execute an agent with the given prompt and return response lines.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        aid (str): Agent ID
        message (AgentMessageInput): Input message for the agent
        thread_id (str): Thread ID for the agent execution
        debug (bool): Enable debug mode

    Returns:
        list[str]: Formatted response lines including timing information

    Example Response Lines:
        [
            "[ Input: ]\n\n user question \n\n-------------------\n",
            "[ Agent: ]\n agent response",
            "\n------------------- agent cost: 0.123 seconds\n",
            "Total time cost: 1.234 seconds"
        ]
    """
    stream_config = {"configurable": {"thread_id": thread_id}}
    resp_debug = [f"Thread ID: {thread_id}\n\n-------------------\n"]
    resp = []
    start = time.perf_counter()
    last = start

    # user input
    resp_debug.append(
        f"[ Input: ]\n\n {message.text}\n{'\n'.join(message.images)}\n-------------------\n"
    )

    # cold start
    if aid not in agents:
        initialize_agent(aid)
        resp_debug.append("[ Agent cold start ... ]")
        resp_debug.append(
            f"\n------------------- start cost: {time.perf_counter() - last:.3f} seconds\n"
        )
        last = time.perf_counter()

    executor: CompiledGraph = agents[aid]
    # message
    content = [
        {"type": "text", "text": message.text},
    ]
    content.extend(
        [
            {"type": "image_url", "image_url": {"url": image_url}}
            for image_url in message.images
        ]
    )
    # debug prompt
    if debug:
        # get the agent from the database
        with get_session() as db:
            try:
                agent: Agent = db.exec(select(Agent).filter(Agent.id == aid)).one()
            except NoResultFound:
                # Handle the case where the user is not found
                raise HTTPException(status_code=404, detail="Agent not found")
            except SQLAlchemyError as e:
                # Handle other SQLAlchemy-related errors
                logger.error(e)
                raise HTTPException(status_code=500, detail=str(e))
        try:
            resp_debug_append = "\n===================\n\n[ system ]\n"
            resp_debug_append += agent_prompt(agent)
            snap = executor.get_state(stream_config)
            if snap.values and "messages" in snap.values:
                for msg in snap.values["messages"]:
                    resp_debug_append += f"[ {msg.type} ]\n{msg.content}\n\n"
            if agent.prompt_append:
                resp_debug_append += "[ system ]\n"
                resp_debug_append += agent.prompt_append
        except Exception as e:
            logger.error(e)
            resp_debug_append = ""
    # run
    for chunk in executor.stream(
            {"messages": [HumanMessage(content=content)]}, stream_config
    ):
        if "agent" in chunk:
            v = chunk["agent"]["messages"][0].content
            if v:
                resp_debug.append("[ Agent: ]\n")
                resp_debug.append(v)
                resp.append(v)
            else:
                resp_debug.append("[ Agent is thinking ... ]")
            resp_debug.append(
                f"\n------------------- agent cost: {time.perf_counter() - last:.3f} seconds\n"
            )
            last = time.perf_counter()
        elif "tools" in chunk:
            resp_debug.append("[ Skill running ... ]\n")
            resp_debug.append(chunk["tools"]["messages"][0].content)
            resp_debug.append(
                f"\n------------------- skill cost: {time.perf_counter() - last:.3f} seconds\n"
            )
            last = time.perf_counter()

    total_time = time.perf_counter() - start
    resp_debug.append(f"Total time cost: {total_time:.3f} seconds")
    if debug:
        resp_debug.append(resp_debug_append)
        return resp_debug
    else:
        return resp
