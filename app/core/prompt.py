import json

from app.config.config import config
from models.agent import Agent, AgentData


def agent_prompt(agent: Agent, agent_data: AgentData) -> str:
    prompt = "# SYSTEM PROMPT\n\n"
    if config.system_prompt:
        prompt += config.system_prompt + "\n\n"
    prompt += "You are an AI agent built using IntentKit.\n"
    prompt += "Your tools are called 'skills'.\n"
    prompt += "If your skill fails to execute due to a technical error ask the user to try again later, don't retry by yourself. If someone asks you to do something you can't do with your currently available skills, you must say so, recommend them to submit their feedback to the IntentKit team at https://github.com/crestalnetwork/intentkit. Be concise and helpful with your responses.\n"
    if agent.name:
        prompt += f"Your name is {agent.name}.\n"
    if agent.ticker:
        prompt += f"Your ticker symbol is {agent.ticker}.\n"
    if agent_data:
        if agent_data.twitter_id:
            prompt += f"Your twitter id is {agent_data.twitter_id}, never reply or retweet yourself.\n"
        if agent_data.twitter_username:
            prompt += f"Your twitter username is {agent_data.twitter_username}.\n"
        if agent_data.twitter_name:
            prompt += f"Your twitter name is {agent_data.twitter_name}.\n"
        if agent_data.twitter_is_verified:
            prompt += "Your twitter account is verified.\n"
        else:
            prompt += "Your twitter account is not verified.\n"
        if agent_data.telegram_id:
            prompt += f"Your telegram bot id is {agent_data.telegram_id}.\n"
        if agent_data.telegram_username:
            prompt += f"Your telegram bot username is {agent_data.telegram_username}.\n"
        if agent_data.telegram_name:
            prompt += f"Your telegram bot name is {agent_data.telegram_name}.\n"
        # CDP
        if agent_data.cdp_wallet_data:
            network_id = agent.network_id or agent.cdp_network_id
            wallet_data = json.loads(agent_data.cdp_wallet_data)
            prompt += f"Your wallet address in {network_id} is {wallet_data['default_address_id']} .\n"
    prompt += "\n"
    if agent.purpose:
        prompt += f"## Purpose\n\n{agent.purpose}\n\n"
    if agent.personality:
        prompt += f"## Personality\n\n{agent.personality}\n\n"
    if agent.principles:
        prompt += f"## Principles\n\n{agent.principles}\n\n"
    if agent.prompt:
        prompt += f"## Initial Rules\n\n{agent.prompt}\n\n"
    if agent.skills and "enso" in agent.skills and agent.skills["enso"].get("enabled"):
        prompt += """## ENSO Skills Guide\n\nYou are integrated with the Enso API. You can use enso_get_tokens to retrieve token information,
        including APY, Protocol Slug, Symbol, Address, Decimals, and underlying tokens. When interacting with token amounts,
        ensure to multiply input amounts by the token's decimal places and divide output amounts by the token's decimals. 
        Utilize enso_route_shortcut to find the best swap or deposit route. Set broadcast_request to True only when the 
        user explicitly requests a transaction broadcast. Insufficient funds or insufficient spending approval can cause 
        Route Shortcut broadcasts to fail. To avoid this, use the enso_broadcast_wallet_approve tool that requires explicit 
        user confirmation before broadcasting any approval transactions for security reasons.\n\n"""
    return prompt
