"""Discord bot pool agent item."""
from intentkit.models.agent import Agent


class BotPoolAgentItem:
    """Represents an agent's Discord bot metadata in the pool."""

    def __init__(self, agent: Agent):
        self._token = agent.discord_config.get("token")
        if not self._token:
            raise ValueError("Token cannot be empty for agent item")

        self._id = agent.id
        self._updated_at = agent.updated_at

    @property
    def id(self):
        return self._id

    @property
    def token(self):
        return self._token

    @property
    def updated_at(self):
        return self._updated_at

    @updated_at.setter
    def updated_at(self, val):
        self._updated_at = val
