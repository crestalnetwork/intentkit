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
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from twitter_langchain import TwitterApiWrapper, TwitterToolkit

from app.config.config import config
from app.models.db import Agent, get_coon, get_db
from skill_sets import get_skill_set
from skills.common import get_common_skill
from skills.crestal import get_crestal_skill

logger = logging.getLogger(__name__)

# Global variable to cache all agent executors
agents = {}


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
    db = next(get_db())
    # get the agent from the database
    try:
        agent: Agent = db.query(Agent).filter(Agent.id == aid).one()
    except NoResultFound:
        # Handle the case where the user is not found
        raise HTTPException(status_code=404, detail="Agent not found")
    except SQLAlchemyError as e:
        # Handle other SQLAlchemy-related errors
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))
    # Initialize LLM.
    llm = ChatOpenAI(model_name=agent.model, openai_api_key=config.openai_api_key)

    # Load tools
    tools: list[BaseTool] = []

    # Configure CDP Agentkit Langchain Extension.
    if agent.cdp_enabled:
        values = {
            "cdp_api_key_name": config.cdp_api_key_name,
            "cdp_api_key_private_key": config.cdp_api_key_private_key,
            "network_id": getattr(agent, "cdp_network_id", "base-sepolia"),
        }
        if agent.cdp_wallet_data:
            # If there is a persisted agentic wallet, load it and pass to the CDP Agentkit Wrapper.
            values["cdp_wallet_data"] = agent.cdp_wallet_data
        agentkit = CdpAgentkitWrapper(**values)
        # save the wallet after first create
        if not agent.cdp_wallet_data:
            agent.cdp_wallet_data = agentkit.export_wallet()
            db.add(agent)
            db.commit()
        # Initialize CDP Agentkit Toolkit and get tools.
        cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
        tools.extend(cdp_toolkit.get_tools())

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

    # Initialize CDP Agentkit Twitter Langchain
    if agent.twitter_enabled:
        wrapper = TwitterApiWrapper(**agent.twitter_config)
        toolkit = TwitterToolkit.from_twitter_api_wrapper(wrapper)
        tools.extend(toolkit.get_tools())

    # filter the duplicate tools
    tools = list({tool.name: tool for tool in tools}.values())

    # log all tools
    for tool in tools:
        logger.info(f"[{aid}] loaded tool: {tool.name}")

    # Store buffered conversation history in memory.
    memory = PostgresSaver(get_coon())
    memory.setup()

    prompt = ""
    if agent.name:
        prompt = f"Your name is {agent.name}. "

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

    # Create ReAct Agent using the LLM and CDP Agentkit tools.
    agents[aid] = create_react_agent(
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=prompt,
    )


def execute_agent(aid: str, prompt: str, thread_id: str) -> list[str]:
    """Execute an agent with the given prompt and return response lines.

    This function:
    1. Configures execution context with thread ID
    2. Initializes agent if not in cache
    3. Streams agent execution results
    4. Formats and times the execution steps

    Args:
        aid (str): Agent ID
        prompt (str): Input prompt for the agent
        thread_id (str): Thread ID for the agent execution

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
    config = {"configurable": {"thread_id": thread_id}}
    resp = []
    start = time.perf_counter()
    last = start

    # user input
    resp.append(f"[ Input: ]\n\n {prompt}\n\n-------------------\n")

    # cold start
    if aid not in agents:
        initialize_agent(aid)
        resp.append(f"[ Agent cold start ... ]")
        resp.append(
            f"\n------------------- start cost: {time.perf_counter() - last:.3f} seconds\n"
        )
        last = time.perf_counter()

    executor = agents[aid]
    # run
    for chunk in executor.stream({"messages": [HumanMessage(content=prompt)]}, config):
        if "agent" in chunk:
            v = chunk["agent"]["messages"][0].content
            if v:
                resp.append("[ Agent: ]\n")
                resp.append(v)
            else:
                resp.append("[ Agent is thinking ... ]")
            resp.append(
                f"\n------------------- agent cost: {time.perf_counter() - last:.3f} seconds\n"
            )
            last = time.perf_counter()
        elif "tools" in chunk:
            resp.append("[ Skill running ... ]\n")
            resp.append(chunk["tools"]["messages"][0].content)
            resp.append(
                f"\n------------------- skill cost: {time.perf_counter() - last:.3f} seconds\n"
            )
            last = time.perf_counter()

    total_time = time.perf_counter() - start
    resp.append(f"Total time cost: {total_time:.3f} seconds")
    return resp