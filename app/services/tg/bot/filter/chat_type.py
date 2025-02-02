import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message

logger = logging.getLogger(__name__)


class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_type: str | list):
        self.chat_type = chat_type

    async def __call__(self, message: Message) -> bool:
        try:
            if isinstance(self.chat_type, str):
                return message.chat.type == self.chat_type
            else:
                return message.chat.type in self.chat_type
        except Exception as e:
            logger.error(f"failed to filter chat types: {str(e)}")
            return False


class GroupOnlyFilter(ChatTypeFilter):
    def __init__(self):
        super().__init__(["group", "supergroup"])
