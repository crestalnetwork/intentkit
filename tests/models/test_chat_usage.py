import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from intentkit.config.base import Base
from intentkit.models.chat import ChatMessageTable, sum_thread_token_usage


@pytest_asyncio.fixture()
async def chat_message_engine(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[ChatMessageTable.__table__]
        )

    yield db_engine


def _message(msg_id: str, chat_id: str, input_tokens: int, cached: int):
    return ChatMessageTable(
        id=msg_id,
        agent_id="agent-1",
        chat_id=chat_id,
        author_id="agent-1",
        author_type="agent",
        message="hi",
        input_tokens=input_tokens,
        cached_input_tokens=cached,
    )


@pytest.mark.asyncio
async def test_sum_thread_token_usage(chat_message_engine):
    session_factory = async_sessionmaker(chat_message_engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(_message("m1", "chat-1", 100, 40))
        session.add(_message("m2", "chat-1", 200, 100))
        # Different thread: must not be counted.
        session.add(_message("m3", "chat-2", 999, 999))
        await session.commit()

    assert await sum_thread_token_usage("agent-1", "chat-1") == (300, 140)


@pytest.mark.asyncio
async def test_sum_thread_token_usage_empty_thread(chat_message_engine):
    assert await sum_thread_token_usage("agent-1", "no-messages") == (0, 0)
