import logging

from aiogram.filters import BaseFilter
from aiogram.types import ContentType, Message

logger = logging.getLogger(__name__)


class ContentTypeFilter(BaseFilter):
    def __init__(self, content_types: ContentType | list):
        self.content_types = content_types

    async def __call__(self, message: Message) -> bool:
        try:
            return message.content_type in self.content_types
        except Exception as e:
            logger.error(f"failed to filter content types: {str(e)}")
            return False


class TextOnlyFilter(ContentTypeFilter):
    def __init__(self):
        super().__init__([ContentType.TEXT])
