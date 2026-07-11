"""Tests for team wallets: model CRUD, provisioning rules, agent binding."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from intentkit.config.base import Base
from intentkit.core.team.wallet import (
    create_team_wallet,
    delete_team_wallet,
    set_wallet_safe_token_spending_limit,
    update_team_wallet,
)
from intentkit.models.agent import Agent, AgentVisibility
from intentkit.models.team import Team
from intentkit.models.wallet import TeamWallet, TeamWalletTable
from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets import list_agent_team_wallets, resolve_team_wallet


@pytest_asyncio.fixture()
async def wallet_tables(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[TeamWalletTable.__table__]
        )
    yield


@pytest_asyncio.fixture()
async def agent_table(db_engine):
    from intentkit.models.agent.db import AgentTable

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[AgentTable.__table__])
    yield


async def _add_agent_row(
    agent_id: str, *, tools: list[str] | None, team_id: str | None = "team-1"
) -> None:
    from intentkit.config.db import get_session
    from intentkit.models.agent.db import AgentTable

    async with get_session() as db:
        db.add(
            AgentTable(
                id=agent_id,
                name=agent_id,
                model="gpt-4o",
                owner="user-1",
                team_id=team_id,
                tools=tools,
            )
        )
        await db.commit()


def _build_agent(team_id: str | None = "team-1") -> Agent:
    now = datetime.now()
    return Agent(
        id="agent-1",
        name="Test Agent",
        description="A test agent",
        model="gpt-4o",
        deployed_at=now,
        updated_at=now,
        created_at=now,
        owner="user-1",
        team_id=team_id,
        tools=None,
        system_prompt="You are a helper.",
        temperature=0.7,
        visibility=AgentVisibility.PRIVATE,
        public_info_updated_at=now,
    )


class TestTeamWalletModel:
    @pytest.mark.asyncio
    async def test_create_and_list(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="main",
            wallet_provider="readonly",
            evm_wallet_address="0xabc",
            created_by="user-1",
        )
        assert wallet.team_id == "team-1"
        assert wallet.wallet_provider == "readonly"

        wallets = await TeamWallet.list_for_team("team-1")
        assert [w.id for w in wallets] == [wallet.id]
        assert await TeamWallet.list_for_team("team-2") == []

    @pytest.mark.asyncio
    async def test_wallet_data_excluded_from_serialization(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="secret",
            wallet_provider="native",
            wallet_data=json.dumps({"private_key": "0xdead"}),
            created_by="user-1",
        )
        dumped = wallet.model_dump()
        assert "wallet_data" not in dumped
        assert wallet.wallet_data_json()["private_key"] == "0xdead"


class TestCreateTeamWallet:
    @pytest.mark.asyncio
    async def test_readonly_requires_address(self, wallet_tables):
        with pytest.raises(IntentKitAPIError) as exc_info:
            await create_team_wallet(
                team_id="team-1",
                name="watch",
                wallet_provider="readonly",
                created_by="user-1",
            )
        assert exc_info.value.key == "ReadonlyAddressRequired"

    @pytest.mark.asyncio
    async def test_readonly_wallet(self, wallet_tables):
        wallet = await create_team_wallet(
            team_id="team-1",
            name="watch",
            wallet_provider="readonly",
            created_by="user-1",
            readonly_address="0xwatch",
        )
        assert wallet.evm_wallet_address == "0xwatch"

    @pytest.mark.asyncio
    async def test_native_wallet(self, wallet_tables):
        wallet = await create_team_wallet(
            team_id="team-1",
            name="hot",
            wallet_provider="native",
            created_by="user-1",
        )
        assert wallet.evm_wallet_address
        data = wallet.wallet_data_json()
        assert data["address"] == wallet.evm_wallet_address
        # 32-byte hex key, with or without 0x prefix
        assert int(data["private_key"], 16)
        assert len(data["private_key"].removeprefix("0x")) == 64

    @pytest.mark.asyncio
    async def test_unsupported_provider(self, wallet_tables):
        with pytest.raises(IntentKitAPIError) as exc_info:
            await create_team_wallet(
                team_id="team-1",
                name="bad",
                wallet_provider="none",
                created_by="user-1",
            )
        assert exc_info.value.key == "UnsupportedWalletProvider"

    @pytest.mark.asyncio
    async def test_privy_requires_privy_user(self, wallet_tables, monkeypatch):
        monkeypatch.setattr(Team, "get_owner", AsyncMock(return_value="user-plain"))
        with pytest.raises(IntentKitAPIError) as exc_info:
            await create_team_wallet(
                team_id="team-1",
                name="privy",
                wallet_provider="privy",
                created_by="user-plain",
            )
        assert exc_info.value.key == "PrivyUserIdMissing"


class TestWalletResolution:
    @pytest.mark.asyncio
    async def test_unknown_address_rejected(self, wallet_tables):
        with pytest.raises(IntentKitAPIError) as exc_info:
            await resolve_team_wallet(_build_agent(), "0xnope")
        assert exc_info.value.key == "WalletNotFound"

    @pytest.mark.asyncio
    async def test_other_team_wallet_rejected(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-2",
            name="other",
            wallet_provider="readonly",
            evm_wallet_address="0xOther",
            created_by="user-2",
        )
        assert wallet.evm_wallet_address is not None
        with pytest.raises(IntentKitAPIError) as exc_info:
            await resolve_team_wallet(_build_agent("team-1"), wallet.evm_wallet_address)
        assert exc_info.value.key == "WalletNotFound"

    @pytest.mark.asyncio
    async def test_own_team_wallet_resolves_case_insensitive(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="mine",
            wallet_provider="readonly",
            evm_wallet_address="0xMiNe",
            created_by="user-1",
        )
        resolved = await resolve_team_wallet(_build_agent("team-1"), "0xmine")
        assert resolved.id == wallet.id

    @pytest.mark.asyncio
    async def test_teamless_agent_uses_system_wallets(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="system",
            name="fallback",
            wallet_provider="readonly",
            evm_wallet_address="0xsys",
            created_by="system",
        )
        resolved = await resolve_team_wallet(_build_agent(None), "0xsys")
        assert resolved.id == wallet.id

    @pytest.mark.asyncio
    async def test_list_team_wallets(self, wallet_tables):
        await TeamWallet.create(
            team_id="team-1",
            name="a",
            wallet_provider="readonly",
            evm_wallet_address="0xa",
            created_by="user-1",
        )
        await TeamWallet.create(
            team_id="team-1",
            name="b",
            wallet_provider="readonly",
            evm_wallet_address="0xb",
            created_by="user-1",
        )
        wallets = await list_agent_team_wallets(_build_agent("team-1"))
        assert [w.name for w in wallets] == ["a", "b"]
        assert await list_agent_team_wallets(_build_agent("team-9")) == []


class TestSafeSpendingLimit:
    @pytest.mark.asyncio
    async def test_requires_safe_wallet(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="not-safe",
            wallet_provider="readonly",
            evm_wallet_address="0xw",
            created_by="user-1",
        )
        with pytest.raises(IntentKitAPIError) as exc_info:
            await set_wallet_safe_token_spending_limit(
                "team-1", wallet.id, "0xtoken", 10.0
            )
        assert exc_info.value.key == "SafeWalletRequired"

    @pytest.mark.asyncio
    async def test_success(self, wallet_tables, monkeypatch):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="safe",
            wallet_provider="safe",
            evm_wallet_address="0xsafe",
            wallet_data=json.dumps(
                {
                    "privy_wallet_id": "privy-wallet-1",
                    "privy_wallet_address": "0xprivy",
                    "smart_wallet_address": "0xsafe",
                    "network_id": "base-mainnet",
                    "rpc_url": "http://rpc.url",
                }
            ),
            created_by="user-1",
        )
        monkeypatch.setattr("intentkit.wallets.privy.PrivyClient", MagicMock())
        set_limit_mock = AsyncMock(return_value={"next_nonce": 1})
        monkeypatch.setattr(
            "intentkit.wallets.privy.set_safe_token_spending_limit",
            set_limit_mock,
        )

        result = await set_wallet_safe_token_spending_limit(
            "team-1", wallet.id, "0x1111111111111111111111111111111111111111", 123.45
        )

        set_limit_mock.assert_awaited_once()
        assert set_limit_mock.await_args is not None
        kwargs = set_limit_mock.await_args.kwargs
        assert kwargs["privy_wallet_id"] == "privy-wallet-1"
        assert kwargs["safe_address"] == "0xsafe"
        assert kwargs["spending_limit"] == 123.45
        assert kwargs["network_id"] == "base-mainnet"
        assert kwargs["rpc_url"] == "http://rpc.url"
        assert result == {"next_nonce": 1}


class TestWalletManagement:
    @pytest.mark.asyncio
    async def test_rename(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="old-name",
            wallet_provider="readonly",
            evm_wallet_address="0xw",
            created_by="user-1",
        )
        renamed = await update_team_wallet("team-1", wallet.id, name="new-name")
        assert renamed.name == "new-name"

    @pytest.mark.asyncio
    async def test_update_default_network(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="main",
            wallet_provider="readonly",
            evm_wallet_address="0xw",
            created_by="user-1",
        )
        assert wallet.network == "base-mainnet"
        updated = await update_team_wallet(
            "team-1", wallet.id, default_network_id="ethereum-mainnet"
        )
        assert updated.default_network_id == "ethereum-mainnet"
        assert updated.network == "ethereum-mainnet"
        # Name untouched when only the network changes
        assert updated.name == "main"

    @pytest.mark.asyncio
    async def test_update_network_rejected_for_smart_wallets(self, wallet_tables):
        """Safe/Privy smart wallets are chain-bound; their network is immutable."""
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="safe",
            wallet_provider="safe",
            default_network_id="base-mainnet",
            evm_wallet_address="0xs",
            created_by="user-1",
        )
        with pytest.raises(IntentKitAPIError) as exc_info:
            await update_team_wallet(
                "team-1", wallet.id, default_network_id="ethereum-mainnet"
            )
        assert exc_info.value.key == "WalletNetworkImmutable"
        # Re-sending the current network is a no-op, not an error
        unchanged = await update_team_wallet(
            "team-1", wallet.id, default_network_id="base-mainnet"
        )
        assert unchanged.network == "base-mainnet"

    @pytest.mark.asyncio
    async def test_rename_to_taken_name_rejected(self, wallet_tables):
        await TeamWallet.create(
            team_id="team-1",
            name="taken",
            wallet_provider="readonly",
            evm_wallet_address="0xa",
            created_by="user-1",
        )
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="mine",
            wallet_provider="readonly",
            evm_wallet_address="0xb",
            created_by="user-1",
        )
        with pytest.raises(IntentKitAPIError) as exc_info:
            await update_team_wallet("team-1", wallet.id, name="taken")
        assert exc_info.value.key == "WalletNameTaken"

    @pytest.mark.asyncio
    async def test_rename_other_team_wallet_rejected(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-2",
            name="other",
            wallet_provider="readonly",
            evm_wallet_address="0xo",
            created_by="user-2",
        )
        with pytest.raises(IntentKitAPIError) as exc_info:
            await update_team_wallet("team-1", wallet.id, name="stolen")
        assert exc_info.value.key == "WalletNotFound"

    @pytest.mark.asyncio
    async def test_delete_with_remaining_wallets(self, wallet_tables, agent_table):
        keep = await TeamWallet.create(
            team_id="team-1",
            name="keep",
            wallet_provider="readonly",
            evm_wallet_address="0xk",
            created_by="user-1",
        )
        gone = await TeamWallet.create(
            team_id="team-1",
            name="gone",
            wallet_provider="readonly",
            evm_wallet_address="0xg",
            created_by="user-1",
        )
        await delete_team_wallet("team-1", gone.id)
        wallets = await TeamWallet.list_for_team("team-1")
        assert [w.id for w in wallets] == [keep.id]

    @pytest.mark.asyncio
    async def test_delete_last_wallet_blocked_by_web3_agents(
        self, wallet_tables, agent_table
    ):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="last",
            wallet_provider="readonly",
            evm_wallet_address="0xl",
            created_by="user-1",
        )
        await _add_agent_row("agent-web3", tools=["erc20_transfer"])
        with pytest.raises(IntentKitAPIError) as exc_info:
            await delete_team_wallet("team-1", wallet.id)
        assert exc_info.value.key == "WalletRequiredByAgents"

    @pytest.mark.asyncio
    async def test_delete_last_system_wallet_blocked_by_teamless_web3_agents(
        self, wallet_tables, agent_table
    ):
        """Teamless agents belong to the synthetic system team by convention;
        the last-wallet guard must count them too."""
        wallet = await TeamWallet.create(
            team_id="system",
            name="sys",
            wallet_provider="readonly",
            evm_wallet_address="0xs",
            created_by="system",
        )
        await _add_agent_row("agent-orphan", tools=["erc20_transfer"], team_id=None)
        with pytest.raises(IntentKitAPIError) as exc_info:
            await delete_team_wallet("system", wallet.id)
        assert exc_info.value.key == "WalletRequiredByAgents"

    @pytest.mark.asyncio
    async def test_delete_last_wallet_ok_without_web3_agents(
        self, wallet_tables, agent_table
    ):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="last",
            wallet_provider="readonly",
            evm_wallet_address="0xl",
            created_by="user-1",
        )
        await _add_agent_row("agent-plain", tools=["http_get"])
        await delete_team_wallet("team-1", wallet.id)
        assert await TeamWallet.list_for_team("team-1") == []
