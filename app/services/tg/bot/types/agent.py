from datetime import datetime

from intentkit.models.agent import Agent

from app.services.tg.utils.cleanup import clean_token_str


class BotPoolAgentItem:
    def __init__(self, agent: Agent):
        if not agent.telegram_config:
            raise ValueError("telegram config can not be empty")

        token = agent.telegram_config.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("token can not be empty for agent item")

        self._bot_token: str = clean_token_str(token)
        self._agent: Agent = agent

        self._id: str = agent.id
        self._updated_at: datetime | None = agent.deployed_at or agent.updated_at

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def id(self) -> str:
        return self._id

    @property
    def bot_token(self) -> str:
        return self._bot_token

    @property
    def updated_at(self) -> datetime | None:
        return self._updated_at

    @updated_at.setter
    def updated_at(self, val: datetime | None):
        self._updated_at = val
