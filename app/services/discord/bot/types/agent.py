from datetime import datetime

from intentkit.models.agent import Agent


class BotPoolAgentItem:
    """Represents an agent's Discord bot metadata in the pool."""

    _token: str | None
    _id: str
    _updated_at: datetime | None

    def __init__(self, agent: Agent):
        self._token = (agent.discord_config or {}).get("token")
        if not self._token:
            raise ValueError("Token cannot be empty for agent item")

        self._id = agent.id
        self._updated_at = agent.deployed_at or agent.updated_at

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
    def updated_at(self, val: datetime | None):
        self._updated_at = val
