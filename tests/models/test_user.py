import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from intentkit.config.base import Base
from intentkit.models.user import User, UserTable


@pytest_asyncio.fixture()
async def sqlite_engine():
    from intentkit.config import db as db_module

    test_engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.engine = test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[UserTable.__table__])

    try:
        yield test_engine
    finally:
        await test_engine.dispose()
        db_module.engine = None


@pytest.mark.asyncio
async def test_get_by_evm_wallet(sqlite_engine):
    session_factory = async_sessionmaker(sqlite_engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            UserTable(
                id="user_with_wallet",
                evm_wallet_address="0x123",
            )
        )
        session.add(
            UserTable(
                id="user_id_only",
            )
        )
        await session.commit()

    direct_match = await User.get_by_evm_wallet("0x123")
    assert direct_match is not None
    assert direct_match.id == "user_with_wallet"

    id_fallback = await User.get_by_evm_wallet("user_id_only")
    assert id_fallback is not None
    assert id_fallback.id == "user_id_only"

    missing = await User.get_by_evm_wallet("0xnotfound")
    assert missing is None
