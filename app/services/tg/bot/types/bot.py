from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from app.services.tg.bot.types.kind import is_valid_kind
from app.services.tg.utils.cleanup import clean_token_str
from models.agent import Agent


class BotPoolItem:
    def __init__(self, agent: Agent):
        self._agent_id = agent.id

        self._token = clean_token_str(agent.telegram_config.get("token"))
        if self._token is None:
            raise ValueError("bot token can not be empty")

        self._kind = agent.telegram_config.get("kind")
        if self._kind is None:
            raise ValueError("bot kind can not be empty")

        if not is_valid_kind(int(self.kind)):
            raise ValueError("bot kind is not valid")

        self.update_conf(agent.telegram_config)

        self._bot = Bot(
            token=self._token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

    def update_conf(self, cfg):
        self._is_public_memory = cfg.get("group_memory_public", True)
        self._whitelist_chat_ids = cfg.get("whitelist_chat_ids")
        self._greeting_group = cfg.get(
            "greeting_group",
            "🤖 Hi Everybody, 🎉\nGreetings, traveler of the digital realm! You've just awakened the mighty powers of this chat bot. Brace yourself for an adventure filled with wit, wisdom, and possibly a few jokes.",
        )
        self._greeting_user = cfg.get(
            "greeting_user",
            "🤖 Hi, 🎉\nGreetings, traveler of the digital realm! You've just awakened the mighty powers of this chat bot. Brace yourself for an adventure filled with wit, wisdom, and possibly a few jokes.",
        )

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

    @property
    def greeting_group(self):
        return self._greeting_group

    @property
    def greeting_user(self):
        return self._greeting_user
