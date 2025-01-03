import logging

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    TokenBasedRequestHandler,
    setup_application,
)
from aiohttp import web

from app.models.agent import Agent
from tg.bot.kind.ai_relayer.router import general_router
from tg.bot.kind.god.router import god_router
from tg.bot.kind.god.startup import GOD_BOT_PATH, GOD_BOT_TOKEN, on_startup
from tg.bot.types.agent import BotPoolAgentItem
from tg.bot.types.bot import BotPoolItem
from tg.bot.types.kind import Kind
from tg.bot.types.router_obj import RouterObj

logger = logging.getLogger(__name__)

BOTS_PATH = "/webhook/tgbot/{kind}/{bot_token}"

_bots = {}
_agent_bots = {}


def bot_by_token(token) -> BotPoolItem:
    return _bots.get(token)


def set_cache_bot(bot: BotPoolItem):
    _bots[bot.token] = bot


def agent_by_id(agent_id) -> BotPoolAgentItem:
    return _agent_bots.get(agent_id)


def set_cache_agent(agent: BotPoolAgentItem):
    _agent_bots[agent.id] = agent


def agent_thread_id(agent_id, group_memory_public, chat_id):
    if group_memory_public:
        return f"{agent_id}-public"
    return f"{agent_id}-telegram-{chat_id}"


async def health_handler(request):
    """Health check endpoint handler."""
    return web.json_response({"status": "healthy"})


class BotPool:
    def __init__(self, base_url):
        self.app = web.Application()
        self.app.router.add_get("/health", health_handler)
        self.base_url = f"{base_url}{BOTS_PATH}"
        self.routers = {
            Kind.AiRelayer: RouterObj(general_router),
        }

    def init_god_bot(self):
        if GOD_BOT_TOKEN:
            try:
                logger.info("Initialize god bot...")
                self.god_bot = Bot(
                    token=GOD_BOT_TOKEN,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )
                storage = MemoryStorage()
                # In order to use RedisStorage you need to use Key Builder with bot ID:
                # storage = RedisStorage.from_url(TG_REDIS_DSN, key_builder=DefaultKeyBuilder(with_bot_id=True))
                dp = Dispatcher(storage=storage)
                dp.include_router(god_router)
                dp.startup.register(on_startup)
                SimpleRequestHandler(dispatcher=dp, bot=self.god_bot).register(
                    self.app, path=GOD_BOT_PATH
                )
                setup_application(self.app, dp, bot=self.god_bot)
            except Exception as e:
                logger.error(f"failed to init god bot: {e}")

    def init_all_dispatchers(self):
        logger.info("Initialize all dispatchers...")
        for kind, b in self.routers.items():
            storage = MemoryStorage()
            # In order to use RedisStorage you need to use Key Builder with bot ID:
            # storage = RedisStorage.from_url(TG_REDIS_DSN, key_builder=DefaultKeyBuilder(with_bot_id=True))
            b.set_dispatcher(Dispatcher(storage=storage))
            b.get_dispatcher().include_router(b.get_router())
            TokenBasedRequestHandler(
                dispatcher=b.get_dispatcher(),
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            ).register(
                self.app,
                path=BOTS_PATH.format(kind=kind.value, bot_token="{bot_token}"),
            )
            setup_application(self.app, b.get_dispatcher())
            logger.info(f"{kind} router initialized...")

    async def init_new_bot(self, agent: Agent):
        try:
            bot_item = BotPoolItem(agent)
            agent_item = BotPoolAgentItem(agent)

            await bot_item.bot.delete_webhook(drop_pending_updates=True)
            await bot_item.bot.set_webhook(
                self.base_url.format(kind=bot_item.kind, bot_token=bot_item.token)
            )

            set_cache_bot(bot_item)
            set_cache_agent(agent_item)

            logger.info(
                f"bot for agent {agent.id} with token {bot_item.token} initialized..."
            )

        except ValueError as e:
            logger.warning(
                f"bot for agent {agent.id} did not started because of invalid data. err: {e}"
            )
        except Exception as e:
            logger.error(f"failed to init new bot for agent {agent.id}: {e}")

    async def change_bot_token(self, agent: Agent):
        try:
            new_bot_item = BotPoolItem(agent)
            new_agent_item = BotPoolAgentItem(agent)

            old_agent_item = agent_by_id(agent.id)
            old_cached_bot_item = bot_by_token(old_agent_item.bot_token)

            if old_cached_bot_item and old_cached_bot_item.bot:
                old_bot = old_cached_bot_item.bot
            else:
                old_bot = Bot(
                    token=old_cached_bot_item.token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )

            await old_bot.session.close()
            await old_bot.delete_webhook(drop_pending_updates=True)

            await new_bot_item.bot.delete_webhook(drop_pending_updates=True)
            await new_bot_item.bot.set_webhook(
                self.base_url.format(
                    kind=new_bot_item.kind, bot_token=new_bot_item.token
                )
            )

            del _bots[old_cached_bot_item.token]
            set_cache_bot(new_bot_item)
            set_cache_agent(new_agent_item)

            logger.info(
                f"bot for agent {agent.id} with token {old_agent_item.bot_token} changed to {new_bot_item.token}..."
            )

        except ValueError as e:
            logger.warning(
                f"bot for agent {agent.id} token did not changed because of invalid data. err: {e}"
            )
        except Exception as e:
            logger.error(f"failed to change bot token for agent {agent.id}: {str(e)}")

    async def stop_bot(self, agent: Agent):
        try:
            token = agent.telegram_config.get("token")
            if token is None:
                logger.warning(
                    f"bot for agent {agent.id} token did not stopped because of empty token"
                )
                return

            cached_bot_item = bot_by_token(agent.telegram_config["token"])
            if cached_bot_item and cached_bot_item.bot:
                bot = cached_bot_item.bot
            else:
                bot = Bot(
                    token=cached_bot_item.token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )

            await bot.session.close()
            await bot.delete_webhook(drop_pending_updates=True)

            del _bots[token]
            del _agent_bots[agent.id]

            logger.info(f"Bot with token {token} for agent {agent.id} stopped...")
        except Exception as e:
            logger.error(f"failed to stop the bot for agent {agent.id}: {e}")

    async def modify_config(self, agent):
        if not agent.telegram_enabled:
            await self.stop_bot(agent)
            return

        try:
            old_agent_item = agent_by_id(agent.id)
            old_bot_item = bot_by_token(old_agent_item.bot_token)
            old_bot_item.update_conf(agent.telegram_config)
            old_agent_item.updated_at = agent.updated_at

            if old_bot_item.kind != agent.telegram_config.get("kind"):
                await self.stop_bot(agent)
                await self.init_new_bot(agent)
            logger.info(
                f"configurations of the bot with token {agent.telegram_config["token"]} for agent {agent.id} updated..."
            )

        except ValueError as e:
            logger.warning(
                f"bot for agent {agent.id} config did not changed because of invalid data. err: {e}"
            )
        except Exception as e:
            logger.error(
                f"failed to change the configs of the bot for agent {agent.id}: {str(e)}"
            )

    def start(self, asyncio_loop, host, port):
        web.run_app(self.app, loop=asyncio_loop, host=host, port=port)
