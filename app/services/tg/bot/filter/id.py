import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.services.tg.bot import pool

logger = logging.getLogger(__name__)


class WhitelistedChatIDsFilter(BaseFilter):
    def __init__(self):
        pass

    async def __call__(self, message: Message) -> bool:
        try:
            whitelist = pool.bot_by_token(message.bot.token).whitelist_chat_ids
            if whitelist and len(whitelist) > 0:
                return message.chat.id in whitelist or str(message.chat.id) in whitelist

            return True

        except Exception as e:
            logger.error(f"failed to filter whitelisted chat ids: {str(e)}")
            return False
