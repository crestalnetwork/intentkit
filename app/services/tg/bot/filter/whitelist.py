import importlib
import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message

logger = logging.getLogger(__name__)


class WhitelistedChatIDsFilter(BaseFilter):
    def __init__(self):
        pass

    async def __call__(self, message: Message) -> bool:  # pyright: ignore[reportImplicitOverride]
        pool = importlib.import_module("app.services.tg.bot.pool")

        try:
            if not message.bot or not message.bot.token:
                return False
            bot = pool.bot_by_token(message.bot.token)
            if not bot:
                return False
            whitelist = bot.whitelist_chat_ids
            if whitelist and len(whitelist) > 0:
                return message.chat.id in whitelist

            return True

        except Exception as e:
            logger.error(f"failed to filter whitelisted chat ids: {str(e)}")
            return False
