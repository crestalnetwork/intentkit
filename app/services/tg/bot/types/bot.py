from typing import NotRequired, TypedDict

from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from app.services.tg.utils.cleanup import clean_token_str
from models.agent import Agent


class TelegramConfig(TypedDict):
    token: str
    kind: NotRequired[int] = 1
    group_memory_public: NotRequired[bool]
    whitelist_chat_ids: NotRequired[list[int]]
    greeting_group: NotRequired[str]
    greeting_user: NotRequired[str]


class BotPoolItem:
    def __init__(self, agent: Agent):
        self._agent_id = agent.id
        self._agent_owner = agent.owner

        self._token = clean_token_str(agent.telegram_config.get("token"))
        if self._token is None:
            raise ValueError("bot token can not be empty")

        self._kind = 1

        self.update_conf(agent.telegram_config)

        self._bot = Bot(
            token=self._token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    def update_conf(self, cfg: TelegramConfig):
        self._is_public_memory = cfg.get("group_memory_public", True)
        self._whitelist_chat_ids = cfg.get("whitelist_chat_ids")
        self._greeting_group = cfg.get(
            "greeting_group",
            "Glory to the Nation!\nFind me on https://nation.fun",
        )
        self._greeting_user = cfg.get(
            "greeting_user",
            "Glory to the Nation!\nFind me on https://nation.fun",
        )

    @property
    def agent_id(self):
        return self._agent_id

    @property
    def agent_owner(self):
        return self._agent_owner

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

    @property
    def greeting_group(self):
        return self._greeting_group

    @property
    def greeting_user(self):
        return self._greeting_user
