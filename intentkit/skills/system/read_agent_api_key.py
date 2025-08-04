from pydantic import BaseModel, Field

from intentkit.skills.system.base import SystemBaseTool


class ReadAgentApiKeyInput(BaseModel):
    """Input model for read_agent_api_key skill."""

    pass


class ReadAgentApiKeyOutput(BaseModel):
    """Output model for read_agent_api_key skill."""

    api_key: str = Field(description="The private API key for the agent (sk-)")
    api_key_public: str = Field(description="The public API key for the agent (pk-)")
    is_new: bool = Field(description="Whether new API keys were generated")
    open_api_base_url: str = Field(description="The base URL for the API")
    api_endpoint: str = Field(description="The full API endpoint URL")


class ReadAgentApiKey(SystemBaseTool):
    """Skill to retrieve or generate an API key for the agent."""

    name: str = "system_read_agent_api_key"
    description: str = (
        "Retrieve the API keys for the agent.  "
        "Returns both private (sk-) and public (pk-) API keys.  "
        "Private API key can access all skills (public and owner-only).  "
        "Public API key can only access public skills.  "
        "Make sure to tell the user the base URL and endpoint.  "
        "Tell user in OpenAI sdk or Desktop client like Cherry Studio, input the base URL and API key.  "
        "Always use markdown code block to wrap the API keys, base URL, and endpoint.  "
        "Tell user to check more doc in https://github.com/crestalnetwork/intentkit/blob/main/docs/agent_api.md "
    )
    args_schema = ReadAgentApiKeyInput

    async def _arun(self, **kwargs) -> ReadAgentApiKeyOutput:
        """Retrieve or generate an API key for the agent."""
        # Get context from runnable config to access agent.id
        context = self.get_context()
        agent_id = context.agent_id

        # Get agent data from skill store
        agent_data = await self.skill_store.get_agent_data(agent_id)

        # Get API base URL from system config
        open_api_base_url = self.skill_store.get_system_config("open_api_base_url")
        api_endpoint = f"{open_api_base_url}/v1/chat/completions"

        # Check if API keys exist
        if agent_data.api_key and agent_data.api_key_public:
            return ReadAgentApiKeyOutput(
                api_key=agent_data.api_key,
                api_key_public=agent_data.api_key_public,
                is_new=False,
                open_api_base_url=open_api_base_url,
                api_endpoint=api_endpoint,
            )

        # Generate new API keys if any are missing
        new_api_key = agent_data.api_key or self._generate_api_key()
        new_public_api_key = (
            agent_data.api_key_public or self._generate_public_api_key()
        )

        # Save the API keys to agent data
        update_data = {}
        if not agent_data.api_key:
            update_data["api_key"] = new_api_key
        if not agent_data.api_key_public:
            update_data["api_key_public"] = new_public_api_key

        if update_data:
            await self.skill_store.set_agent_data(agent_id, update_data)

        return ReadAgentApiKeyOutput(
            api_key=new_api_key,
            api_key_public=new_public_api_key,
            is_new=bool(update_data),
            open_api_base_url=open_api_base_url,
            api_endpoint=api_endpoint,
        )
