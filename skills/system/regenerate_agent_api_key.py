from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.system.base import SystemBaseTool


class RegenerateAgentApiKeyInput(BaseModel):
    """Input model for regenerate_agent_api_key skill."""

    pass


class RegenerateAgentApiKeyOutput(BaseModel):
    """Output model for regenerate_agent_api_key skill."""

    api_key: str = Field(description="The new API key for the agent")
    previous_key_existed: bool = Field(description="Whether a previous API key existed")
    open_api_base_url: str = Field(description="The base URL for the API")
    api_endpoint: str = Field(description="The full API endpoint URL")


class RegenerateAgentApiKey(SystemBaseTool):
    """Skill to regenerate and reset the API key for the agent."""

    name: str = "system_regenerate_agent_api_key"
    description: str = (
        "Generate a new API key for the agent, revoke any existing key. "
        "Make sure to tell the user the base URL and endpoint. "
        "Tell user in OpenAI sdk or Desktop client like Cherry Studio, input the base URL and API key."
    )
    args_schema = RegenerateAgentApiKeyInput

    async def _arun(
        self, config: RunnableConfig, **kwargs
    ) -> RegenerateAgentApiKeyOutput:
        """Generate and set a new API key for the agent."""
        # Get context from runnable config to access agent.id
        context = self.context_from_config(config)
        agent_id = context.agent.id

        # Get agent data from skill store
        agent_data = await self.skill_store.get_agent_data(agent_id)

        if not agent_data:
            raise ValueError(f"Agent data not found for agent_id: {agent_id}")

        # Get API base URL from system config
        open_api_base_url = self.skill_store.get_system_config("open_api_base_url")
        api_endpoint = f"{open_api_base_url}/v1/chat/completions"

        # Check if previous API key existed
        previous_key_existed = bool(agent_data.api_key)

        # Generate new API key
        new_api_key = self._generate_api_key()

        # Save the new API key to agent data (overwrites existing)
        await self.skill_store.set_agent_data(agent_id, {"api_key": new_api_key})

        return RegenerateAgentApiKeyOutput(
            api_key=new_api_key,
            previous_key_existed=previous_key_existed,
            open_api_base_url=open_api_base_url,
            api_endpoint=api_endpoint,
        )
