from typing import Any, Dict, Union

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.token import TokenValidationError, validate_token

god_router = Router()


def is_bot_token(value: str) -> Union[bool, Dict[str, Any]]:
    try:
        validate_token(value)
    except TokenValidationError:
        return False
    return True


@god_router.message(Command("add", magic=F.args.func(is_bot_token)))
async def command_add_bot(message: Message, command: CommandObject, bot: Bot) -> Any:
    new_bot = Bot(token=command.args, session=bot.session)
    try:
        bot_user = await new_bot.get_me()
    except TelegramUnauthorizedError:
        return message.answer("Invalid token")
    # await new_bot.delete_webhook(drop_pending_updates=True)
    # await new_bot.set_webhook(OTHER_BOTS_URL.format(bot_token=command.args))
    return await message.answer(
        f"Your Bot is @{bot_user.username} but, it should be registered in Intent Kit first!"
    )
