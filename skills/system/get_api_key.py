from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.system.base import SystemBaseTool


class GetApiKeyInput(BaseModel):
    """Input model for get_api_key skill."""

    pass


class GetApiKeyOutput(BaseModel):
    """Output model for get_api_key skill."""

    api_key: str = Field(description="The API key for the agent")
    is_new: bool = Field(description="Whether a new API key was generated")


class GetApiKey(SystemBaseTool):
    """Skill to retrieve or generate an API key for the agent."""

    name: str = "system_get_api_key"
    description: str = "Retrieve the API key for the agent. If no API key exists, generates and sets a new one."
    args_schema = GetApiKeyInput

    async def _arun(self, config: RunnableConfig, **kwargs) -> GetApiKeyOutput:
        """Retrieve or generate an API key for the agent."""
        # Get context from runnable config to access agent.id
        context = self.context_from_config(config)
        agent_id = context.agent.id

        # Get agent data from skill store
        agent_data = await self.skill_store.get_agent_data(agent_id)

        if not agent_data:
            raise ValueError(f"Agent data not found for agent_id: {agent_id}")

        # Check if API key exists
        if agent_data.api_key:
            return GetApiKeyOutput(api_key=agent_data.api_key, is_new=False)

        # Generate new API key if none exists
        new_api_key = self._generate_api_key()

        # Save the new API key to agent data
        await self.skill_store.set_agent_data(agent_id, {"api_key": new_api_key})

        return GetApiKeyOutput(api_key=new_api_key, is_new=True)
