from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.system.base import SystemBaseTool


class ResetApiKeyInput(BaseModel):
    """Input model for reset_api_key skill."""

    pass


class ResetApiKeyOutput(BaseModel):
    """Output model for reset_api_key skill."""

    api_key: str = Field(description="The new API key for the agent")
    previous_key_existed: bool = Field(description="Whether a previous API key existed")


class ResetApiKey(SystemBaseTool):
    """Skill to regenerate and reset the API key for the agent."""

    name: str = "system_reset_api_key"
    description: str = "Generate a new API key for the agent, revoke any existing key. Tell the user the new key."
    args_schema = ResetApiKeyInput

    async def _arun(self, config: RunnableConfig, **kwargs) -> ResetApiKeyOutput:
        """Generate and set a new API key for the agent."""
        # Get context from runnable config to access agent.id
        context = self.context_from_config(config)
        agent_id = context.agent.id

        # Get agent data from skill store
        agent_data = await self.skill_store.get_agent_data(agent_id)

        if not agent_data:
            raise ValueError(f"Agent data not found for agent_id: {agent_id}")

        # Check if previous API key existed
        previous_key_existed = bool(agent_data.api_key)

        # Generate new API key
        new_api_key = self._generate_api_key()

        # Save the new API key to agent data (overwrites existing)
        await self.skill_store.set_agent_data(agent_id, {"api_key": new_api_key})

        return ResetApiKeyOutput(
            api_key=new_api_key, previous_key_existed=previous_key_existed
        )
