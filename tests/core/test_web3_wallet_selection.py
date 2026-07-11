"""Tests for the wallet-by-address model: signing guard, prompt injection,
and wallet tool gating."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from intentkit.config.base import Base
from intentkit.core.agent.management import _validate_wallet_tools
from intentkit.core.prompt import _build_wallet_section
from intentkit.models.agent import Agent, AgentVisibility
from intentkit.models.wallet import TeamWallet, TeamWalletTable
from intentkit.tools.onchain import IntentKitOnChainTool
from intentkit.utils.error import IntentKitAPIError


@pytest_asyncio.fixture()
async def wallet_tables(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[TeamWalletTable.__table__]
        )
    yield


def _build_agent(
    team_id: str | None = "team-1", tools: list[str] | None = None
) -> Agent:
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
        tools=tools,
        prompt="You are a helper.",
        temperature=0.7,
        visibility=AgentVisibility.PRIVATE,
        public_info_updated_at=now,
    )


class _DummyOnChainTool(IntentKitOnChainTool):
    name: str = "dummy_onchain"
    description: str = "dummy"
    category: str = "dummy"

    async def _arun(self) -> str:  # pragma: no cover - never invoked
        return "ok"


class TestSigningGuard:
    def _tool_with_context(self, is_own_team: bool) -> _DummyOnChainTool:
        tool = _DummyOnChainTool()
        context = MagicMock()
        context.is_own_team = is_own_team
        context.agent = _build_agent()
        object.__setattr__(tool, "get_context", lambda: context)
        return tool

    def test_guest_context_cannot_sign(self):
        from langchain_core.tools.base import ToolException

        tool = self._tool_with_context(is_own_team=False)
        with pytest.raises(ToolException, match="Signing is not allowed"):
            tool.ensure_signing_allowed()

    def test_own_team_context_can_sign(self):
        tool = self._tool_with_context(is_own_team=True)
        tool.ensure_signing_allowed()  # must not raise

    @pytest.mark.asyncio
    async def test_guest_context_can_still_read(self, wallet_tables):
        wallet = await TeamWallet.create(
            team_id="team-1",
            name="readable",
            wallet_provider="readonly",
            evm_wallet_address="0xread",
            created_by="user-1",
        )
        tool = self._tool_with_context(is_own_team=False)
        resolved = await tool.resolve_wallet("0xread")
        assert resolved.id == wallet.id

    @pytest.mark.asyncio
    async def test_signing_helpers_are_guarded(self, wallet_tables):
        from langchain_core.tools.base import ToolException

        await TeamWallet.create(
            team_id="team-1",
            name="hot",
            wallet_provider="native",
            evm_wallet_address="0xhot",
            wallet_data='{"address": "0xhot", "private_key": "00", "network_id": "base-mainnet"}',
            created_by="user-1",
        )
        tool = self._tool_with_context(is_own_team=False)
        with pytest.raises(ToolException):
            await tool.get_wallet_signer("0xhot")
        with pytest.raises(ToolException):
            await tool.get_wallet_provider("0xhot")
        with pytest.raises(ToolException):
            await tool.get_unified_wallet("0xhot")


def _prompt_context(is_own_team: bool = True) -> MagicMock:
    context = MagicMock()
    context.is_own_team = is_own_team
    return context


class TestPromptWalletSection:
    @pytest.mark.asyncio
    async def test_no_web3_tools_no_section(self, wallet_tables):
        agent = _build_agent(tools=["http_get"])
        assert await _build_wallet_section(agent, _prompt_context()) == ""

    @pytest.mark.asyncio
    async def test_no_wallets_no_section(self, wallet_tables):
        agent = _build_agent(tools=["erc20_transfer"])
        assert await _build_wallet_section(agent, _prompt_context()) == ""

    @pytest.mark.asyncio
    async def test_guest_with_only_signing_tools_gets_no_section(self, wallet_tables):
        """Signing web3 tools are not bound for guests, so the wallet list
        (and its usage instructions) must not be injected either."""
        await TeamWallet.create(
            team_id="team-1",
            name="main",
            wallet_provider="cdp",
            evm_wallet_address="0xaaa",
            created_by="user-1",
        )
        agent = _build_agent(tools=["erc20_transfer"])
        assert await _build_wallet_section(agent, _prompt_context(False)) == ""

    @pytest.mark.asyncio
    async def test_guest_with_read_tools_gets_section(self, wallet_tables):
        await TeamWallet.create(
            team_id="team-1",
            name="main",
            wallet_provider="cdp",
            evm_wallet_address="0xaaa",
            created_by="user-1",
        )
        agent = _build_agent(tools=["erc20_get_balance", "erc20_transfer"])
        section = await _build_wallet_section(agent, _prompt_context(False))
        assert "Team Wallets" in section
        assert "`0xaaa`" in section

    @pytest.mark.asyncio
    async def test_lists_all_team_wallets(self, wallet_tables):
        await TeamWallet.create(
            team_id="team-1",
            name="trading",
            wallet_provider="cdp",
            default_network_id="base-mainnet",
            evm_wallet_address="0xaaa",
            created_by="user-1",
        )
        await TeamWallet.create(
            team_id="team-1",
            name="treasury",
            wallet_provider="safe",
            default_network_id="base-mainnet",
            evm_wallet_address="0xbbb",
            created_by="user-1",
        )
        agent = _build_agent(tools=["erc20_transfer"])
        section = await _build_wallet_section(agent, _prompt_context())
        assert "Team Wallets" in section
        assert "trading" in section and "`0xaaa`" in section
        assert "treasury" in section and "`0xbbb`" in section
        assert "wallet_address" in section


class TestWalletToolGating:
    @pytest.mark.asyncio
    async def test_rejects_wallet_tools_without_wallets(self, wallet_tables):
        with pytest.raises(IntentKitAPIError) as exc_info:
            await _validate_wallet_tools(["erc20_transfer"], "team-1")
        assert exc_info.value.key == "Web3ToolsRequireWallet"

    @pytest.mark.asyncio
    async def test_allows_wallet_tools_with_wallet(self, wallet_tables):
        await TeamWallet.create(
            team_id="team-1",
            name="main",
            wallet_provider="readonly",
            evm_wallet_address="0xw",
            created_by="user-1",
        )
        await _validate_wallet_tools(["erc20_transfer"], "team-1")  # must not raise

    @pytest.mark.asyncio
    async def test_non_wallet_tools_never_gated(self, wallet_tables):
        await _validate_wallet_tools(["http_get", "firecrawl_scrape"], "team-1")

    @pytest.mark.asyncio
    async def test_empty_tools_never_gated(self, wallet_tables):
        await _validate_wallet_tools(None, "team-1")
        await _validate_wallet_tools([], "team-1")
