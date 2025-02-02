from app.services.tg.utils.cleanup import clean_token_str
from models.agent import Agent


class BotPoolAgentItem:
    def __init__(self, agent: Agent):
        self._bot_token = clean_token_str(agent.telegram_config.get("token"))
        if self._bot_token is None:
            raise ValueError("token can not be empty for agent item")

        self._id = agent.id
        self._updated_at = agent.updated_at

    @property
    def id(self):
        return self._id

    @property
    def bot_token(self):
        return self._bot_token

    @property
    def updated_at(self):
        return self._updated_at

    @updated_at.setter
    def updated_at(self, val):
        self._updated_at = val
