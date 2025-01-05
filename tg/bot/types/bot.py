from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from app.models.agent import Agent


class BotPoolItem:
    def __init__(self, agent: Agent):
        self._agent_id = agent.id

        self._token = agent.telegram_config.get("token")
        if self._token is None:
            raise ValueError("bot token can not be empty")

        self._kind = agent.telegram_config.get("kind")
        if self._kind is None:
            raise ValueError("bot kind can not be empty")

        self.update_conf(agent.telegram_config)

        self._bot = Bot(
            token=self._token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    def update_conf(self, cfg):
        self._is_public_memory = cfg.get("group_memory_public", True)
        self._whitelist_chat_ids = cfg.get("whitelist_chat_ids")

    @property
    def agent_id(self):
        return self._agent_id

    @property
    def token(self):
        return self._token

    @property
    def kind(self):
        return self._kind

    @property
    def bot(self):
        return self._bot

    # optional props

    @property
    def is_public_memory(self):
        return self._is_public_memory

    @property
    def whitelist_chat_ids(self):
        return self._whitelist_chat_ids