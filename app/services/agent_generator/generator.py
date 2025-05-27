"""Agent Generator Service.

This module provides functionality to generate agent schemas from natural language prompts
using OpenAI's API.
"""

import logging
import os
from typing import Dict, List, Optional, Any

import httpx
from openai import OpenAI

from models.agent import AgentCreate, AgentUpdate, Agent

logger = logging.getLogger(__name__)

# Default system prompt for OpenAI
SYSTEM_PROMPT = """
You are an expert in IntentKit agent creation. Your task is to analyze a user's natural language prompt
and generate a valid agent schema with appropriate skills enabled.

For skills, use the following format:
{
  "skill_name": {
    "enabled": true,
    "states": {
      "state_name": "public"
    }
  }
}

Only include skills that are specifically relevant to the user's request.
"""

# Mapping of capability keywords to IntentKit skills
SKILL_MAPPING = {
    # Web search related
    "web search": {"tavily": ["tavily_search"]},
    "search": {"tavily": ["tavily_search"]},
    "internet": {"tavily": ["tavily_search"]},
    "find information": {"tavily": ["tavily_search"]},
    "research": {"tavily": ["tavily_search"]},
    "extract content": {"tavily": ["tavily_extract"]},
    "website content": {"tavily": ["tavily_extract"]},
    
    # Social media - Twitter
    "twitter": {"twitter": ["post_tweet", "search_tweets"]},
    "tweet": {"twitter": ["post_tweet"]},
    "posting on twitter": {"twitter": ["post_tweet"]},
    "x.com": {"twitter": ["post_tweet", "search_tweets"]},
    "monitor twitter": {"twitter": ["search_tweets"]},
    
    # Social media - Slack
    "slack": {"slack": ["post_message"]},
    "team communication": {"slack": ["post_message"]},
    "work chat": {"slack": ["post_message"]},
    
    # Social media - Telegram
    "telegram": {"telegram": ["post_message"]},
    "telegram bot": {"telegram": ["post_message"]},
    "telegram message": {"telegram": ["post_message"]},
    
    # Cryptocurrency
    "crypto": {"cryptocompare": ["get_price"]},
    "cryptocurrency": {"cryptocompare": ["get_price"]},
    "token prices": {"cryptocompare": ["get_price"]},
    "coin prices": {"cryptocompare": ["get_price"]},
    "crypto news": {"cryptocompare": ["get_news"]},
    "cryptocurrency news": {"cryptocompare": ["get_news"]},
    
    # Crypto market data
    "crypto panic": {"cryptopanic": ["get_posts"]},
    "crypto market news": {"cryptopanic": ["get_posts"]},
    
    # DEX trading
    "dex": {"dexscreener": ["search_pairs"]},
    "dex screener": {"dexscreener": ["search_pairs"]},
    "token pairs": {"dexscreener": ["search_pairs"]},
    "trading pairs": {"dexscreener": ["search_pairs"]},
    
    # DeFi analytics
    "defi": {"defillama": ["get_protocol", "get_tvl"]},
    "defillama": {"defillama": ["get_protocol", "get_tvl"]},
    "protocol tvl": {"defillama": ["get_tvl"]},
    "tvl": {"defillama": ["get_tvl"]},
    "protocol data": {"defillama": ["get_protocol"]},
    
    # Blockchain analytics
    "dune": {"dune_analytics": ["query"]},
    "dune analytics": {"dune_analytics": ["query"]},
    "on-chain data": {"dune_analytics": ["query"]},
    "blockchain analytics": {"dune_analytics": ["query"]},
    
    # DappLooker analytics
    "dapp analytics": {"dapplooker": ["query"]},
    "dapplooker": {"dapplooker": ["query"]},
    
    # Blockchain integration
    "wallet": {"cdp": ["get_balance", "transfer"]},
    "blockchain": {"cdp": ["get_balance", "transfer"]},
    "web3": {"cdp": ["get_balance", "transfer"]},
    "token transfer": {"cdp": ["transfer"]},
    "check balance": {"cdp": ["get_balance"]},
    
    # GitHub integration
    "github": {"github": ["search_repositories", "search_issues"]},
    "git": {"github": ["search_repositories", "search_issues"]},
    "code repository": {"github": ["search_repositories"]},
    "issues": {"github": ["search_issues"]},
    
    # Portfolio management
    "portfolio": {"portfolio": ["get_portfolio"]},
    "investments": {"portfolio": ["get_portfolio"]},
    "portfolio tracker": {"portfolio": ["get_portfolio"]},
    
    # Token info
    "token info": {"token": ["get_token_info"]},
    "token data": {"token": ["get_token_info"]},
    
    # Blockchain data
    "moralis": {"moralis": ["get_token_price", "get_wallet_tokens"]},
    "wallet tokens": {"moralis": ["get_wallet_tokens"]},
    
    # Chainlist info
    "chain info": {"chainlist": ["get_chain"]},
    "network info": {"chainlist": ["get_chain"]},
    "blockchain networks": {"chainlist": ["get_chain"]},
    
    # Voice synthesis
    "text to speech": {"unrealspeech": ["create_speech"]},
    "voice generation": {"unrealspeech": ["create_speech"]},
    "audio generation": {"unrealspeech": ["create_speech"]},
    
    # Image generation
    "image generation": {"venice_image": ["generate_image"]},
    "create image": {"venice_image": ["generate_image"]},
    "generate image": {"venice_image": ["generate_image"]},
    
    # OpenAI integration
    "vision": {"openai": ["vision"]},
    "image analysis": {"openai": ["vision"]},
    
    # Common utilities
    "time": {"common": ["current_time"]},
    "current time": {"common": ["current_time"]},
    "weather": {"common": ["weather"]},
    "check weather": {"common": ["weather"]},
    "random": {"common": ["random"]},
    "generate random": {"common": ["random"]},
}


async def generate_agent_schema(
    prompt: str, 
    model_override: Optional[str] = None,
    temperature_override: Optional[float] = None
) -> Dict[str, Any]:
    """Generate an agent schema from a natural language prompt.
    
    Args:
        prompt: The natural language prompt describing the agent
        model_override: Optional model override
        temperature_override: Optional temperature override
        
    Returns:
        A dictionary containing the complete agent schema
    """
    # Get OpenAI API key from environment or configuration
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # Create OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Identify relevant skills from the prompt
    skills_config = await identify_skills(prompt, client)
    
    # Generate agent attributes
    attributes = await generate_agent_attributes(prompt, skills_config, client)
    
    # Combine into full schema
    schema = {
        **attributes,
        "skills": skills_config,
        "model": model_override or "gpt-4.1-nano",
        "temperature": temperature_override or 0.7,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }
    
    return schema


async def identify_skills(prompt: str, client: OpenAI) -> Dict[str, Any]:
    """Identify relevant skills from the prompt.
    
    Args:
        prompt: The natural language prompt
        client: OpenAI client
        
    Returns:
        Dict containing skill configurations
    """
    # First attempt: Use keyword matching for common capabilities
    skills_config = keyword_match_skills(prompt)
    
    # If no skills found or for more complex prompts, use OpenAI
    if not skills_config:
        skills_config = await openai_match_skills(prompt, client)
    
    return skills_config


def keyword_match_skills(prompt: str) -> Dict[str, Any]:
    """Match skills using keyword matching.
    
    Args:
        prompt: The natural language prompt
        
    Returns:
        Dict containing skill configurations
    """
    skills_config = {}
    prompt_lower = prompt.lower()
    
    for keyword, skill_mapping in SKILL_MAPPING.items():
        if keyword.lower() in prompt_lower:
            for skill_name, states in skill_mapping.items():
                if skill_name not in skills_config:
                    skills_config[skill_name] = {
                        "enabled": True,
                        "states": {}
                    }
                
                for state in states:
                    skills_config[skill_name]["states"][state] = "public"
    
    return skills_config


async def openai_match_skills(prompt: str, client: OpenAI) -> Dict[str, Any]:
    """Match skills using OpenAI's API.
    
    Args:
        prompt: The natural language prompt
        client: OpenAI client
        
    Returns:
        Dict containing skill configurations
    """
    system_prompt = """
    You are an AI skill analyzer. Your task is to identify which IntentKit skills are needed
    based on a prompt describing an agent's capabilities.
    
    Available skills and their states:
    - tavily: Web search capabilities (states: tavily_search, tavily_extract)
    - twitter: Twitter integration (states: post_tweet, search_tweets)
    - slack: Slack integration (states: post_message)
    - telegram: Telegram integration (states: post_message)
    - cryptocompare: Cryptocurrency data (states: get_price, get_news)
    - cryptopanic: Crypto market news (states: get_posts)
    - dexscreener: DEX trading pairs (states: search_pairs)
    - defillama: DeFi analytics (states: get_protocol, get_tvl)
    - dune_analytics: Blockchain analytics (states: query)
    - dapplooker: Dapp analytics (states: query)
    - cdp: Blockchain wallet (states: get_balance, transfer)
    - github: GitHub integration (states: search_repositories, search_issues)
    - portfolio: Portfolio management (states: get_portfolio)
    - token: Token information (states: get_token_info)
    - moralis: Blockchain data (states: get_token_price, get_wallet_tokens)
    - chainlist: Chain information (states: get_chain)
    - unrealspeech: Voice synthesis (states: create_speech)
    - venice_image: Image generation (states: generate_image)
    - openai: OpenAI integration (states: vision)
    - common: Utility functions (states: current_time, weather, random)
    
    Respond with ONLY a JSON object mapping skill names to their configurations, like this:
    {
      "skill_name": {
        "enabled": true,
        "states": {
          "state_name": "public"
        }
      }
    }
    
    Only include skills that are specifically relevant to the prompt.
    """
    
    user_prompt = f"""
    Identify the necessary skills for an agent described as:
    "{prompt}"
    """
    
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
    )
    
    try:
        skills_config = response.choices[0].message.content
        # Parse the JSON response
        import json
        skills_config = json.loads(skills_config)
        return skills_config
    except Exception as e:
        logger.error(f"Error parsing OpenAI response: {e}")
        # Return empty dict as fallback
        return {}


async def generate_agent_attributes(prompt: str, skills_config: Dict[str, Any], client: OpenAI) -> Dict[str, Any]:
    """Generate agent attributes from the prompt.
    
    Args:
        prompt: The natural language prompt
        skills_config: Dict of identified skills
        client: OpenAI client
        
    Returns:
        Dict containing agent attributes (name, purpose, personality, principles)
    """
    # Create a string representation of skills for the prompt
    skills_text = ""
    for skill_name, config in skills_config.items():
        states = list(config.get("states", {}).keys())
        skills_text += f"- {skill_name}: {', '.join(states)}\n"
    
    system_prompt = """
    You are an AI agent designer. Your task is to create appropriate attributes for an IntentKit agent
    based on a prompt and identified skills.
    
    Generate the following attributes:
    1. name: A concise, descriptive name (max 50 characters)
    2. purpose: A clear statement of the agent's purpose (100-200 words)
    3. personality: A description of the agent's personality traits (100-200 words)
    4. principles: 4-6 guiding principles for the agent (150-250 words)
    
    Do not use level 1 or 2 markdown headings (# or ##) in any field.
    
    Respond with ONLY a JSON object containing these attributes.
    """
    
    user_prompt = f"""
    Create attributes for an agent described as:
    "{prompt}"
    
    With these skills:
    {skills_text}
    """
    
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
    )
    
    try:
        attributes = response.choices[0].message.content
        # Parse the JSON response
        import json
        attributes = json.loads(attributes)
        return attributes
    except Exception as e:
        logger.error(f"Error parsing OpenAI response: {e}")
        # Return basic attributes as fallback
        return {
            "name": "Generated Agent",
            "purpose": "I am an AI assistant designed to help with various tasks.",
            "personality": "I am helpful, knowledgeable, and friendly.",
            "principles": "1. Provide accurate information\n2. Be helpful\n3. Respect user privacy\n4. Be clear and concise"
        }


async def create_agent_from_schema(schema: Dict[str, Any]) -> str:
    """Create a new agent from a schema.
    
    Args:
        schema: Dict containing the agent schema
        
    Returns:
        String containing the agent ID
    """
    try:
        # Convert schema to AgentCreate model
        agent_create = AgentCreate(**schema)
        
        # Create the agent
        agent = await agent_create.create()
        
        return agent.id
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise


async def update_agent_from_schema(agent_id: str, schema: Dict[str, Any]) -> None:
    """Update an existing agent from a schema.
    
    Args:
        agent_id: ID of the agent to update
        schema: Dict containing the agent schema
    """
    try:
        # Get existing agent
        existing_agent = await Agent.get(agent_id)
        if not existing_agent:
            raise ValueError(f"Agent with ID {agent_id} not found")
            
        # Convert schema to AgentUpdate model
        agent_update = AgentUpdate(**schema)
        
        # Update the agent
        await agent_update.update(agent_id)
    except Exception as e:
        logger.error(f"Failed to update agent: {str(e)}")
        raise 