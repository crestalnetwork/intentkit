import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message

logger = logging.getLogger(__name__)


class NoBotFilter(BaseFilter):
    def __init__(self):
        pass

    async def __call__(self, message: Message) -> bool:  # pyright: ignore[reportImplicitOverride]
        try:
            if not message.from_user:
                return True
            return not message.from_user.is_bot

        except Exception as e:
            logger.error(f"failed to filter no bots: {str(e)}")
            return False
