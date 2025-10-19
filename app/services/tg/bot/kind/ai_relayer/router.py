import inspect
import logging

import telegramify_markdown
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReactionTypeEmoji
from epyxid import XID

from intentkit.core.client import execute_agent
from intentkit.models.chat import AuthorType, ChatMessageCreate
from intentkit.models.user import User
from intentkit.utils.slack_alert import send_slack_message

from app.services.tg.bot import pool
from app.services.tg.bot.filter.chat_type import GroupOnlyFilter
from app.services.tg.bot.filter.content_type import TextOnlyFilter
from app.services.tg.bot.filter.id import WhitelistedChatIDsFilter
from app.services.tg.bot.filter.no_bot import NoBotFilter
from app.services.tg.utils.cleanup import remove_bot_name

logger = logging.getLogger(__name__)


async def get_user_id(from_user) -> str:
    """
    Extract user_id from telegram message from_user.

    Args:
        from_user: Telegram user object from message.from_user

    Returns:
        str: User ID, either from database lookup or fallback to username/user_id
    """
    if from_user and from_user.username:
        user = await User.get_by_tg(from_user.username)
        if user:
            return user.id
        else:
            return from_user.username
    elif from_user:
        return str(from_user.id)
    else:
        raise ValueError("No valid user information available")


def cur_func_name():
    return inspect.stack()[1][3]


def cur_mod_name():
    return inspect.getmodule(inspect.stack()[1][0]).__name__


general_router = Router()


@general_router.message(Command("chat_id"), NoBotFilter(), TextOnlyFilter())
async def command_chat_id(message: Message) -> None:
    try:
        await message.answer(text=str(message.chat.id))
    except Exception as e:
        logger.warning(
            f"error processing in function:{cur_func_name()}, token:{message.bot.token} err: {str(e)}"
        )


## group commands and messages


@general_router.message(
    CommandStart(),
    NoBotFilter(),
    WhitelistedChatIDsFilter(),
    GroupOnlyFilter(),
    TextOnlyFilter(),
)
async def gp_command_start(message: Message):
    try:
        cached_bot_item = pool.bot_by_token(message.bot.token)
        await message.answer(text=cached_bot_item.greeting_group)
    except Exception as e:
        logger.warning(
            f"error processing in function:{cur_func_name()}, token:{message.bot.token} err: {str(e)}"
        )


@general_router.message(
    WhitelistedChatIDsFilter(), NoBotFilter(), GroupOnlyFilter(), TextOnlyFilter()
)
async def gp_process_message(message: Message) -> None:
    bot = await message.bot.get_me()
    if (
        message.reply_to_message
        and message.reply_to_message.from_user.id == message.bot.id
    ) or bot.username in message.text:
        cached_bot_item = pool.bot_by_token(message.bot.token)
        if cached_bot_item is None:
            logger.warning(f"bot with token {message.bot.token} not found in cache.")
            return

        try:
            user_id = await get_user_id(message.from_user)
            is_owner = (
                cached_bot_item._owner == message.from_user.username
                if message.from_user
                else False
            )
            logger.info(f"message from: {message.from_user}")
        except ValueError:
            is_owner = False
            logger.error(
                f"telegram message from user without username: {message.from_user}"
            )
            return

        # Add processing reaction
        await message.react([ReactionTypeEmoji(emoji="🤔")])

        try:
            # remove bot name tag from text
            message_text = remove_bot_name(bot.username, message.text)
            if len(message_text) > 65535:
                send_slack_message(
                    (
                        "Message too long from telegram.\n"
                        f"length: {len(message_text)}\n"
                        f"chat_id:{message.chat.id}\n"
                        f"agent:{cached_bot_item.agent_id}\n"
                        f"user:{user_id}\n"
                        f"content:{message_text[:100]}..."
                    )
                )

            # Wrap message with group context and username
            username = (
                message.from_user.username
                if message.from_user and message.from_user.username
                else "Unknown"
            )
            wrapped_message = f"[Group Message from @{username}]: {message_text}"

            input = ChatMessageCreate(
                id=str(XID()),
                agent_id=cached_bot_item.agent_id,
                chat_id=pool.agent_chat_id(
                    cached_bot_item.is_public_memory, message.chat.id
                ),
                user_id=cached_bot_item.agent_owner if is_owner else user_id,
                author_id=user_id,
                author_type=AuthorType.TELEGRAM,
                thread_type=AuthorType.TELEGRAM,
                message=wrapped_message,
            )
            response = await execute_agent(input)
            await message.answer(
                text=telegramify_markdown.markdownify(
                    response[-1].message if response else "Server Error"
                ),
                parse_mode="MarkdownV2",
                reply_to_message_id=message.message_id,
            )
        except Exception as e:
            logger.warning(
                f"error processing in function:{cur_func_name()}, token:{message.bot.token}, err={str(e)}"
            )
            await message.answer(
                text="Server Error", reply_to_message_id=message.message_id
            )
        finally:
            # Remove processing reaction
            try:
                await message.react([])
            except Exception as e:
                logger.warning(f"Failed to remove reaction: {str(e)}")


## direct commands and messages


@general_router.message(
    CommandStart(), NoBotFilter(), WhitelistedChatIDsFilter(), TextOnlyFilter()
)
async def command_start(message: Message) -> None:
    try:
        cached_bot_item = pool.bot_by_token(message.bot.token)
        await message.answer(text=cached_bot_item.greeting_user)
    except Exception as e:
        logger.warning(
            f"error processing in function:{cur_func_name()}, token:{message.bot.token} err: {str(e)}"
        )


@general_router.message(
    TextOnlyFilter(),
    NoBotFilter(),
    WhitelistedChatIDsFilter(),
)
async def process_message(message: Message) -> None:
    cached_bot_item = pool.bot_by_token(message.bot.token)
    if cached_bot_item is None:
        logger.warning(f"bot with token {message.bot.token} not found in cache.")
        return

    try:
        user_id = await get_user_id(message.from_user)
        is_owner = (
            cached_bot_item._owner == message.from_user.username
            if message.from_user
            else False
        )
        logger.info(f"message from: {message.from_user}")
    except ValueError:
        is_owner = False
        logger.error(
            f"telegram message from user without username: {message.from_user}"
        )
        return

    # Add processing reaction
    await message.react([ReactionTypeEmoji(emoji="🤔")])

    try:
        if len(message.text) > 65535:
            send_slack_message(
                (
                    "Message too long from telegram.\n"
                    f"length: {len(message.text)}\n"
                    f"chat_id:{message.chat.id}\n"
                    f"agent:{cached_bot_item.agent_id}\n"
                    f"user:{user_id}\n"
                    f"content:{message.text[:100]}..."
                )
            )

        input = ChatMessageCreate(
            id=str(XID()),
            agent_id=cached_bot_item.agent_id,
            chat_id=pool.agent_chat_id(False, message.chat.id),
            user_id=cached_bot_item.agent_owner if is_owner else user_id,
            author_id=user_id,
            author_type=AuthorType.TELEGRAM,
            thread_type=AuthorType.TELEGRAM,
            message=message.text,
        )
        response = await execute_agent(input)
        await message.answer(
            text=telegramify_markdown.markdownify(
                response[-1].message if response else "Server Error"
            ),
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        logger.warning(
            f"error processing in function:{cur_func_name()}, token:{message.bot.token} err:{str(e)}"
        )
        await message.answer(text="Server Error")
    finally:
        # Remove processing reaction
        try:
            await message.react([])
        except Exception as e:
            logger.warning(f"Failed to remove reaction: {str(e)}")
