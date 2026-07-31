"""Unit tests for the team-scoped autonomous core service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from intentkit.core.autonomous import (
    add_autonomous_task,
    claim_autonomous_execution,
    delete_autonomous_task,
    finish_autonomous_execution,
    get_autonomous_execution_messages,
    get_fresh_running_execution,
    list_autonomous_executions,
    list_team_autonomous_tasks,
    update_autonomous_task,
    update_autonomous_task_status,
)
from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousExecution,
    AutonomousExecutionStatus,
    AutonomousTaskStatus,
    AutonomousUpdateRequest,
)
from intentkit.utils.error import IntentKitAPIError


def _fake_row(**overrides):
    base = {
        "id": "task-1",
        "team_id": "team-1",
        "target_agent_id": None,
        "created_by": None,
        "name": None,
        "description": None,
        "cron": "*/5 * * * *",
        "prompt": "p",
        "enabled": True,
        "status": "waiting",
        "next_run_time": None,
        "created_at": None,
        "updated_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_execution_row(**overrides):
    base = {
        "id": "exec-1",
        "task_id": "task-1",
        "team_id": "team-1",
        "agent_id": "agent-x",
        "target_agent_id": "agent-x",
        "chat_id": "autonomous-task-1",
        "message_id": "msg-1",
        "trigger": "cron",
        "triggered_by": None,
        "status": "running",
        "error": None,
        "result": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "credit_cost": None,
        "message_count": 0,
        "cold_start_cost": 0.0,
        "started_at": datetime.now(UTC),
        "finished_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_session():
    """Return (patcher, mock_session) wiring get_session as an async context manager."""
    patcher = patch("intentkit.core.autonomous.get_session")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.rollback = AsyncMock()
    return patcher, mock_session


@pytest.mark.asyncio
async def test_add_task_belongs_to_team():
    patcher, session = _patch_session()
    try:
        req = AutonomousCreateRequest(cron="*/5 * * * *", prompt="do work")
        result = await add_autonomous_task("team-1", req)

        assert result.team_id == "team-1"
        assert result.target_agent_id is None
        assert result.status == AutonomousTaskStatus.WAITING
        assert result.id
        session.add.assert_called_once()
        # The created row carries the caller's id (here: none).
        assert session.add.call_args.args[0].created_by is None
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_add_task_records_creator():
    patcher, session = _patch_session()
    try:
        req = AutonomousCreateRequest(cron="*/5 * * * *", prompt="do work")
        result = await add_autonomous_task("team-1", req, created_by="user-42")
        assert result.created_by == "user-42"
        assert session.add.call_args.args[0].created_by == "user-42"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_add_task_rejects_invalid_cron():
    # Validation happens before any DB work.
    with pytest.raises(IntentKitAPIError):
        await add_autonomous_task(
            "team-1", AutonomousCreateRequest(cron="* * * * *", prompt="p")
        )


@pytest.mark.asyncio
async def test_add_task_rejects_target_agent_not_in_team():
    patcher, session = _patch_session()
    try:
        # Agent lookup returns None -> not in team.
        session.get = AsyncMock(return_value=None)
        with pytest.raises(IntentKitAPIError):
            await add_autonomous_task(
                "team-1",
                AutonomousCreateRequest(
                    cron="*/5 * * * *", prompt="p", target_agent_id="agent-x"
                ),
            )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_add_task_accepts_target_agent_in_team():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(
            return_value=SimpleNamespace(
                id="agent-x", team_id="team-1", archived_at=None
            )
        )
        result = await add_autonomous_task(
            "team-1",
            AutonomousCreateRequest(
                cron="*/5 * * * *", prompt="p", target_agent_id="agent-x"
            ),
        )
        assert result.target_agent_id == "agent-x"
        session.add.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_task_not_found_raises():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(return_value=None)
        with pytest.raises(IntentKitAPIError):
            await update_autonomous_task(
                "team-1", "task-1", AutonomousUpdateRequest(prompt="new")
            )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_task_rejects_foreign_team():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(return_value=_fake_row(team_id="other-team"))
        with pytest.raises(IntentKitAPIError):
            await update_autonomous_task(
                "team-1", "task-1", AutonomousUpdateRequest(prompt="new")
            )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_task_applies_partial_change():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1", prompt="old")
        session.get = AsyncMock(return_value=row)
        result = await update_autonomous_task(
            "team-1", "task-1", AutonomousUpdateRequest(prompt="new")
        )
        assert result.prompt == "new"
        assert row.prompt == "new"
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_unpins_target_agent():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1", target_agent_id="agent-x")
        session.get = AsyncMock(return_value=row)
        # Explicit None must clear the pinned agent (un-pin → lead-orchestrated).
        result = await update_autonomous_task(
            "team-1", "task-1", AutonomousUpdateRequest(target_agent_id=None)
        )
        assert row.target_agent_id is None
        assert result.target_agent_id is None
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_delete_task():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1")
        session.get = AsyncMock(return_value=row)
        await delete_autonomous_task("team-1", "task-1")
        session.delete.assert_awaited_once_with(row)
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_status_single_row():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1")
        session.get = AsyncMock(return_value=row)
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        result = await update_autonomous_task_status(
            "team-1", "task-1", AutonomousTaskStatus.RUNNING, ts
        )
        assert row.status == "running"
        assert row.next_run_time == ts
        assert result.status == AutonomousTaskStatus.RUNNING
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_list_team_tasks_maps_rows():
    patcher, session = _patch_session()
    try:
        session.scalars = AsyncMock(return_value=[_fake_row(id="a"), _fake_row(id="b")])
        tasks = await list_team_autonomous_tasks("team-1")
        assert [t.id for t in tasks] == ["a", "b"]
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_update_status_clears_when_disabled():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1", enabled=False)
        session.get = AsyncMock(return_value=row)
        result = await update_autonomous_task_status(
            "team-1", "task-1", AutonomousTaskStatus.RUNNING, None
        )
        # Disabled tasks always have runtime state cleared.
        assert row.status is None
        assert result.status is None
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_delete_task_removes_execution_history():
    patcher, session = _patch_session()
    try:
        row = _fake_row(team_id="team-1")
        session.get = AsyncMock(return_value=row)
        await delete_autonomous_task("team-1", "task-1")
        # Executions are deleted alongside the task row.
        session.execute.assert_awaited_once()
        session.delete.assert_awaited_once_with(row)
        session.commit.assert_called_once()
    finally:
        patcher.stop()


def _new_execution(**overrides):
    base = {
        "id": "exec-1",
        "task_id": "task-1",
        "team_id": "team-1",
        "agent_id": "agent-x",
        "target_agent_id": "agent-x",
        "chat_id": "autonomous-task-1",
        "message_id": "msg-1",
    }
    base.update(overrides)
    return AutonomousExecution.model_validate(base)


@pytest.mark.asyncio
async def test_claim_execution_inserts_when_slot_free():
    patcher, session = _patch_session()
    try:
        session.scalars = AsyncMock(return_value=[])
        result = await claim_autonomous_execution(_new_execution())

        session.add.assert_called_once()
        added = session.add.call_args.args[0]
        assert added.task_id == "task-1"
        assert added.trigger == "cron"
        assert added.status == "running"
        session.commit.assert_called_once()
        session.refresh.assert_awaited_once()
        assert result is not None
        assert result.id == "exec-1"
        assert result.status == AutonomousExecutionStatus.RUNNING
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_finish_execution_writes_outcome():
    patcher, session = _patch_session()
    try:
        row = _fake_execution_row()
        session.get = AsyncMock(return_value=row)
        result = await finish_autonomous_execution(
            "exec-1",
            AutonomousExecutionStatus.SUCCESS,
            result="all done",
            input_tokens=10,
            output_tokens=20,
            credit_cost=Decimal("1.5"),
            message_count=3,
        )
        assert row.status == "success"
        assert row.result == "all done"
        assert row.input_tokens == 10
        assert row.finished_at is not None
        assert result is not None
        assert result.status == AutonomousExecutionStatus.SUCCESS
        assert result.credit_cost == Decimal("1.5")
        session.commit.assert_called_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_finish_execution_missing_row_returns_none():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(return_value=None)
        result = await finish_autonomous_execution(
            "exec-gone", AutonomousExecutionStatus.SUCCESS
        )
        assert result is None
        session.commit.assert_not_called()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_claim_execution_skips_when_fresh_run_in_progress():
    patcher, session = _patch_session()
    try:
        fresh = _fake_execution_row(started_at=datetime.now(UTC))
        session.scalars = AsyncMock(return_value=[fresh])
        assert await claim_autonomous_execution(_new_execution()) is None
        session.add.assert_not_called()
        session.commit.assert_not_called()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_claim_execution_interrupts_stale_run_and_inserts():
    patcher, session = _patch_session()
    try:
        stale = _fake_execution_row(
            id="exec-old",
            started_at=datetime.now(UTC) - timedelta(hours=2),
        )
        session.scalars = AsyncMock(return_value=[stale])
        result = await claim_autonomous_execution(_new_execution())
        assert stale.status == "error"
        assert stale.error == "interrupted"
        assert stale.finished_at is not None
        # Interrupts are flushed before the new running row is inserted, so
        # the partial unique index slot is free within the same transaction.
        session.flush.assert_awaited_once()
        session.add.assert_called_once()
        session.commit.assert_called_once()
        assert result is not None
        assert result.id == "exec-1"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_claim_execution_loses_insert_race_returns_none():
    patcher, session = _patch_session()
    try:
        session.scalars = AsyncMock(return_value=[])
        session.commit = AsyncMock(
            side_effect=IntegrityError("stmt", {}, Exception("duplicate"))
        )
        assert await claim_autonomous_execution(_new_execution()) is None
        session.rollback.assert_awaited_once()
        session.refresh.assert_not_awaited()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_get_fresh_running_execution_maps_row():
    patcher, session = _patch_session()
    try:
        session.scalar = AsyncMock(return_value=_fake_execution_row())
        result = await get_fresh_running_execution("task-1")
        assert result is not None
        assert result.status == AutonomousExecutionStatus.RUNNING

        session.scalar = AsyncMock(return_value=None)
        assert await get_fresh_running_execution("task-1") is None
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_list_executions_rejects_foreign_team():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(return_value=_fake_row(team_id="other-team"))
        with pytest.raises(IntentKitAPIError):
            await list_autonomous_executions("team-1", "task-1")
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_list_executions_paginates():
    patcher, session = _patch_session()
    try:
        session.get = AsyncMock(return_value=_fake_row(team_id="team-1"))
        # limit+1 rows returned -> has_more with cursor at the last shown row.
        rows = [_fake_execution_row(id=f"exec-{i}") for i in (3, 2, 1)]
        session.scalars = AsyncMock(return_value=rows)
        executions, has_more, next_cursor = await list_autonomous_executions(
            "team-1", "task-1", limit=2
        )
        assert [e.id for e in executions] == ["exec-3", "exec-2"]
        assert has_more is True
        assert next_cursor == "exec-2"

        session.scalars = AsyncMock(return_value=rows[:2])
        executions, has_more, next_cursor = await list_autonomous_executions(
            "team-1", "task-1", limit=2
        )
        assert len(executions) == 2
        assert has_more is False
        assert next_cursor is None
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_execution_messages_filters_by_reply_to():
    patcher, session = _patch_session()
    try:
        task_row = _fake_row(team_id="team-1")
        execution_row = _fake_execution_row(
            chat_id="autonomous-task-1", message_id="msg-1"
        )
        session.get = AsyncMock(side_effect=[task_row, execution_row])

        message_row = SimpleNamespace(
            id="msg-1",
            agent_id="agent-x",
            chat_id="autonomous-task-1",
            user_id="user-1",
            author_id="autonomous",
            author_type="trigger",
            model=None,
            thread_type="trigger",
            reply_to="msg-1",
            message="do work",
            attachments=None,
            tool_calls=None,
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=0,
            time_cost=0.0,
            credit_event_id=None,
            credit_cost=None,
            cold_start_cost=0.0,
            thinking=None,
            app_id=None,
            error_type=None,
            created_at=datetime.now(UTC),
        )
        session.scalars = AsyncMock(return_value=[message_row])

        messages = await get_autonomous_execution_messages("team-1", "task-1", "exec-1")
        assert len(messages) == 1
        assert messages[0].id == "msg-1"
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_execution_messages_rejects_foreign_execution():
    patcher, session = _patch_session()
    try:
        task_row = _fake_row(team_id="team-1")
        execution_row = _fake_execution_row(task_id="other-task")
        session.get = AsyncMock(side_effect=[task_row, execution_row])
        with pytest.raises(IntentKitAPIError):
            await get_autonomous_execution_messages("team-1", "task-1", "exec-1")
    finally:
        patcher.stop()
