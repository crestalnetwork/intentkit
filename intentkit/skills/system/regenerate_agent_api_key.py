from pydantic import BaseModel, Field

from intentkit.skills.system.base import SystemBaseTool


class RegenerateAgentApiKeyInput(BaseModel):
    """Input model for regenerate_agent_api_key skill."""

    pass


class RegenerateAgentApiKeyOutput(BaseModel):
    """Output model for regenerate_agent_api_key skill."""

    api_key: str = Field(description="The new private API key for the agent (sk-)")
    api_key_public: str = Field(
        description="The new public API key for the agent (pk-)"
    )
    previous_key_existed: bool = Field(description="Whether previous API keys existed")
    open_api_base_url: str = Field(description="The base URL for the API")
    api_endpoint: str = Field(description="The full API endpoint URL")


class RegenerateAgentApiKey(SystemBaseTool):
    """Skill to regenerate and reset the API key for the agent."""

    name: str = "system_regenerate_agent_api_key"
    description: str = (
        "Generate new API keys for the agent, revoke any existing keys.  "
        "Generates both private (sk-) and public (pk-) API keys.  "
        "Private API key can access all skills (public and owner-only).  "
        "Public API key can only access public skills.  "
        "Make sure to tell the user the base URL and endpoint.  "
        "Tell user in OpenAI sdk or Desktop client like Cherry Studio, input the base URL and API key.  "
        "Always use markdown code block to wrap the API keys, base URL, and endpoint.  "
        "Tell user to check more doc in https://github.com/crestalnetwork/intentkit/blob/main/docs/agent_api.md "
    )
    args_schema = RegenerateAgentApiKeyInput

    async def _arun(self, **kwargs) -> RegenerateAgentApiKeyOutput:
        """Generate and set a new API key for the agent."""
        # Get context from runnable config to access agent.id
        context = self.get_context()
        agent_id = context.agent_id

        # Get agent data from skill store
        agent_data = await self.skill_store.get_agent_data(agent_id)

        # Get API base URL from system config
        open_api_base_url = self.skill_store.get_system_config("open_api_base_url")
        api_endpoint = f"{open_api_base_url}/v1/chat/completions"

        # Check if previous API keys existed
        previous_key_existed = bool(agent_data.api_key or agent_data.api_key_public)

        # Generate new API keys
        new_api_key = self._generate_api_key()
        new_public_api_key = self._generate_public_api_key()

        # Save the new API keys to agent data (overwrites existing)
        await self.skill_store.set_agent_data(
            agent_id, {"api_key": new_api_key, "api_key_public": new_public_api_key}
        )

        return RegenerateAgentApiKeyOutput(
            api_key=new_api_key,
            api_key_public=new_public_api_key,
            previous_key_existed=previous_key_existed,
            open_api_base_url=open_api_base_url,
            api_endpoint=api_endpoint,
        )
