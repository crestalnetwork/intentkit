import inspect
import json
import logging
from datetime import datetime
from typing import Any

import telegramify_markdown
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReactionTypeEmoji
from epyxid import XID

from intentkit.config.redis import get_redis
from intentkit.core.client import execute_agent
from intentkit.models.chat import AuthorType, ChatMessageCreate
from intentkit.models.user import User
from intentkit.utils.alert import send_alert

from app.services.tg.bot import pool
from app.services.tg.bot.filter.chat_type import GroupOnlyFilter
from app.services.tg.bot.filter.content_type import TextOnlyFilter
from app.services.tg.bot.filter.id import WhitelistedChatIDsFilter
from app.services.tg.bot.filter.no_bot import NoBotFilter
from app.services.tg.utils.cleanup import remove_bot_name

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL = 24 * 60 * 60  # 1 day in seconds
MAX_CACHED_MESSAGES = 20
MAX_CACHE_SIZE_BYTES = 2048  # 2KB


async def cache_message(chat_id: int, agent_id: str, message: Message) -> None:
    """Cache a message in Redis for context retrieval.

    Args:
        chat_id: The chat ID where the message was sent
        agent_id: The agent ID to identify the agent
        message: The message to cache
    """
    redis = get_redis()
    cache_key = f"intentkit:tg_context:{agent_id}:{chat_id}"

    # Prepare message data for caching
    username = (
        message.from_user.username
        if message.from_user and message.from_user.username
        else "Unknown"
    )

    message_data = {
        "text": message.text,
        "username": username,
        "timestamp": datetime.now().isoformat(),
        "message_id": message.message_id,
    }

    # Add to Redis list (right push to maintain chronological order - oldest first)
    await redis.rpush(cache_key, json.dumps(message_data))

    # Trim list to keep only the latest MAX_CACHED_MESSAGES (remove from left)
    await redis.ltrim(cache_key, -MAX_CACHED_MESSAGES, -1)

    # Set expiration
    await redis.expire(cache_key, CACHE_TTL)


async def get_cached_context(chat_id: int, agent_id: str) -> list[dict[str, Any]]:
    """Retrieve cached messages for context.

    Args:
        chat_id: The chat ID to get context for
        agent_id: The agent ID to identify the agent

    Returns:
        List of cached message data, limited by size and count
    """
    redis = get_redis()
    cache_key = f"intentkit:tg_context:{agent_id}:{chat_id}"

    # Get all cached messages (oldest first due to rpush)
    cached_messages = await redis.lrange(cache_key, 0, -1)

    if not cached_messages:
        return []

    # Parse messages and apply size limit
    context_messages = []
    total_size = 0

    for msg_json in cached_messages:
        try:
            msg_data = json.loads(msg_json)
            msg_size = len(json.dumps(msg_data))

            if total_size + msg_size > MAX_CACHE_SIZE_BYTES:
                break

            context_messages.append(msg_data)
            total_size += msg_size

        except json.JSONDecodeError:
            continue

    return context_messages


async def clear_cached_context(chat_id: int, agent_id: str) -> None:
    """Clear cached messages after agent processes them.

    Args:
        chat_id: The chat ID to clear context for
        agent_id: The agent ID to identify the agent
    """
    redis = get_redis()
    cache_key = f"intentkit:tg_context:{agent_id}:{chat_id}"
    await redis.delete(cache_key)


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

    # Check if this message should trigger a bot reply
    should_reply = (
        message.reply_to_message
        and message.reply_to_message.from_user.id == message.bot.id
    ) or bot.username in message.text

    if should_reply:
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
            # Get cached context messages
            context_messages = await get_cached_context(
                message.chat.id, cached_bot_item.agent_id
            )

            # remove bot name tag from text
            message_text = remove_bot_name(bot.username, message.text)
            if len(message_text) > 65535:
                send_alert(
                    "Message too long from telegram.\n"
                    f"length: {len(message_text)}\n"
                    f"chat_id:{message.chat.id}\n"
                    f"agent:{cached_bot_item.agent_id}\n"
                    f"user:{user_id}\n"
                    f"content:{message_text[:100]}..."
                )

            # Wrap message with group context and username
            username = (
                message.from_user.username
                if message.from_user and message.from_user.username
                else "Unknown"
            )

            # Build message with context
            if context_messages:
                context_text = "Recent conversation context:\n"
                # Messages are already in chronological order (oldest first)
                for ctx_msg in context_messages:
                    context_text += f"@{ctx_msg['username']}: {ctx_msg['text']}\n"
                context_text += f"\nCurrent message from @{username}: {message_text}"
                wrapped_message = f"[Group Message with Context]: {context_text}"
            else:
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

            # Clear cached context after successful agent response
            await clear_cached_context(message.chat.id, cached_bot_item.agent_id)

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
    else:
        # This message doesn't trigger a reply, cache it for context
        cached_bot_item = pool.bot_by_token(message.bot.token)
        if cached_bot_item:
            await cache_message(message.chat.id, cached_bot_item.agent_id, message)


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
            send_alert(
                "Message too long from telegram.\n"
                f"length: {len(message.text)}\n"
                f"chat_id:{message.chat.id}\n"
                f"agent:{cached_bot_item.agent_id}\n"
                f"user:{user_id}\n"
                f"content:{message.text[:100]}..."
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
