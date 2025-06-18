from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.system.base import SystemBaseTool


class ReadAgentApiKeyInput(BaseModel):
    """Input model for read_agent_api_key skill."""

    pass


class ReadAgentApiKeyOutput(BaseModel):
    """Output model for read_agent_api_key skill."""

    api_key: str = Field(description="The API key for the agent")
    is_new: bool = Field(description="Whether a new API key was generated")
    open_api_base_url: str = Field(description="The base URL for the API")
    api_endpoint: str = Field(description="The full API endpoint URL")


class ReadAgentApiKey(SystemBaseTool):
    """Skill to retrieve or generate an API key for the agent."""

    name: str = "system_read_agent_api_key"
    description: str = (
        "Retrieve the API key for the agent. "
        "Make sure to tell the user the base URL and endpoint. "
        "Tell user in OpenAI sdk or Desktop client like Cherry Studio, input the base URL and API key."
    )
    args_schema = ReadAgentApiKeyInput

    async def _arun(self, config: RunnableConfig, **kwargs) -> ReadAgentApiKeyOutput:
        """Retrieve or generate an API key for the agent."""
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

        # Check if API key exists
        if agent_data.api_key:
            return ReadAgentApiKeyOutput(
                api_key=agent_data.api_key,
                is_new=False,
                open_api_base_url=open_api_base_url,
                api_endpoint=api_endpoint,
            )

        # Generate new API key if none exists
        new_api_key = self._generate_api_key()

        # Save the new API key to agent data
        await self.skill_store.set_agent_data(agent_id, {"api_key": new_api_key})

        return ReadAgentApiKeyOutput(
            api_key=new_api_key,
            is_new=True,
            open_api_base_url=open_api_base_url,
            api_endpoint=api_endpoint,
        )
