"""Tests for the autonomous task runner's execution branching and recording."""

from contextlib import ExitStack
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from intentkit.models.autonomous import (
    AutonomousExecutionStatus,
    AutonomousExecutionTrigger,
)
from intentkit.models.chat import AuthorType, ChatMessage

MODULE = "app.entrypoints.autonomous"


def _msg(author_type=AuthorType.AGENT, message="done", **overrides):
    base = dict(
        author_type=author_type,
        message=message,
        credit_cost=None,
        tool_calls=None,
        input_tokens=0,
        output_tokens=0,
        cached_input_tokens=0,
        cold_start_cost=0.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _ok_response():
    return [_msg()]


def _patch_runner(stack, *, claimed=True, response=None):
    """Patch the runner's collaborators; returns the mocks that tests assert on."""
    response = response if response is not None else _ok_response()
    clear_memory_mock = stack.enter_context(
        patch(f"{MODULE}.clear_thread_memory", new=AsyncMock())
    )
    stack.enter_context(patch(f"{MODULE}.create_agent_activity", new=AsyncMock()))
    # The claim returns the persisted execution, or None when the task's run
    # slot is taken.
    claim_mock = (
        AsyncMock(side_effect=lambda execution: execution)
        if claimed
        else AsyncMock(return_value=None)
    )
    mocks = SimpleNamespace(
        clear_thread_memory=clear_memory_mock,
        claim=stack.enter_context(
            patch(f"{MODULE}.claim_autonomous_execution", new=claim_mock)
        ),
        finish_execution=stack.enter_context(
            patch(f"{MODULE}.finish_autonomous_execution", new=AsyncMock())
        ),
        execute_agent=stack.enter_context(
            patch(f"{MODULE}.execute_agent", new=AsyncMock(return_value=response))
        ),
        execute_lead=stack.enter_context(
            patch(f"{MODULE}.execute_lead", new=AsyncMock(return_value=response))
        ),
    )
    return mocks


@pytest.mark.asyncio
async def test_runner_direct_path_when_target_agent_set():
    from app.entrypoints.autonomous import run_autonomous_task

    with ExitStack() as stack:
        mocks = _patch_runner(stack)
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
            target_agent_id="agent-x",
        )

        mocks.execute_agent.assert_awaited_once()
        mocks.execute_lead.assert_not_awaited()
        # Every run starts from a clean thread; history is never retained.
        mocks.clear_thread_memory.assert_awaited_once()
        # The direct message targets the agent itself.
        call = mocks.execute_agent.await_args
        assert call is not None
        sent = call.args[0]
        assert sent.agent_id == "agent-x"


@pytest.mark.asyncio
async def test_runner_lead_path_when_no_target_agent():
    from app.entrypoints.autonomous import run_autonomous_task

    with ExitStack() as stack:
        mocks = _patch_runner(stack)
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
            target_agent_id=None,
        )

        mocks.execute_agent.assert_not_awaited()
        mocks.execute_lead.assert_awaited_once()
        # The unconditional clean-thread rule applies to the lead path too.
        mocks.clear_thread_memory.assert_awaited_once()
        call = mocks.execute_lead.await_args
        assert call is not None
        assert call.args[0] == "team-1"
        assert call.args[1] == "user-1"
        # The lead message is attributed to the synthetic team lead agent.
        sent = call.args[2]
        assert sent.agent_id == "team-team-1"


@pytest.mark.asyncio
async def test_runner_skips_when_previous_run_in_progress():
    from app.entrypoints.autonomous import run_autonomous_task

    with ExitStack() as stack:
        mocks = _patch_runner(stack, claimed=False)
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
        )

        mocks.execute_agent.assert_not_awaited()
        mocks.execute_lead.assert_not_awaited()
        mocks.finish_execution.assert_not_awaited()
        # A skipped run must not touch the running conversation's thread.
        mocks.clear_thread_memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_runner_records_successful_execution():
    from app.entrypoints.autonomous import run_autonomous_task

    response = [
        _msg(
            author_type=AuthorType.AGENT,
            message="report ready",
            input_tokens=100,
            output_tokens=50,
            credit_cost=Decimal("2"),
        )
    ]
    with ExitStack() as stack:
        mocks = _patch_runner(stack, response=response)
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
            target_agent_id="agent-x",
            trigger=AutonomousExecutionTrigger.MANUAL,
            triggered_by="user-9",
        )

        # The execution record carries the run's identity and trigger.
        created = mocks.claim.await_args.args[0]
        assert created.task_id == "task-1"
        assert created.team_id == "team-1"
        assert created.agent_id == "agent-x"
        assert created.chat_id == "autonomous-task-1"
        assert created.trigger == AutonomousExecutionTrigger.MANUAL
        assert created.triggered_by == "user-9"
        # The trigger message id is the log lookup key.
        sent = mocks.execute_agent.await_args.args[0]
        assert created.message_id == sent.id

        finish = mocks.finish_execution.await_args
        assert finish.args[1] == AutonomousExecutionStatus.SUCCESS
        assert finish.kwargs["error"] is None
        assert finish.kwargs["result"] == "report ready"
        assert finish.kwargs["input_tokens"] == 100
        assert finish.kwargs["output_tokens"] == 50
        assert finish.kwargs["credit_cost"] == Decimal("2")
        assert finish.kwargs["message_count"] == 1


@pytest.mark.asyncio
async def test_runner_records_error_from_system_message():
    from app.entrypoints.autonomous import run_autonomous_task

    response = [_msg(author_type=AuthorType.SYSTEM, message="quota exceeded")]
    with ExitStack() as stack:
        mocks = _patch_runner(stack, response=response)
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
            target_agent_id="agent-x",
        )

        finish = mocks.finish_execution.await_args
        assert finish.args[1] == AutonomousExecutionStatus.ERROR
        assert "quota exceeded" in finish.kwargs["error"]


@pytest.mark.asyncio
async def test_runner_records_error_on_exception():
    from app.entrypoints.autonomous import run_autonomous_task

    with ExitStack() as stack:
        mocks = _patch_runner(stack)
        mocks.execute_agent.side_effect = RuntimeError("boom")
        await run_autonomous_task(
            team_id="team-1",
            owner_user_id="user-1",
            task_id="task-1",
            prompt="do it",
            target_agent_id="agent-x",
        )

        finish = mocks.finish_execution.await_args
        assert finish.args[1] == AutonomousExecutionStatus.ERROR
        assert "boom" in finish.kwargs["error"]


def test_aggregate_run_stats_sums_tokens_and_credits():
    from app.entrypoints.autonomous import aggregate_run_stats

    resp = [
        _msg(
            author_type=AuthorType.TOOL,
            message="",
            input_tokens=10,
            output_tokens=5,
            cached_input_tokens=2,
            credit_cost=Decimal("1.5"),
            tool_calls=[
                {"name": "search", "credit_cost": Decimal("0.5")},
                {"name": "free_tool"},
            ],
            cold_start_cost=1.25,
        ),
        _msg(
            author_type=AuthorType.AGENT,
            message="x" * 1000,
            input_tokens=20,
            output_tokens=30,
            credit_cost=Decimal("3"),
        ),
    ]
    stats = aggregate_run_stats(cast(list[ChatMessage], resp))
    assert stats["input_tokens"] == 30
    assert stats["output_tokens"] == 35
    assert stats["cached_input_tokens"] == 2
    # LLM costs plus tool-call costs, which are separate credit events.
    assert stats["credit_cost"] == Decimal("5")
    assert stats["message_count"] == 2
    assert stats["cold_start_cost"] == 1.25
    # Final agent reply is truncated for list display.
    assert len(stats["result"]) == 500


def test_aggregate_run_stats_empty_response():
    from app.entrypoints.autonomous import aggregate_run_stats

    stats = aggregate_run_stats([])
    assert stats["credit_cost"] is None
    assert stats["result"] is None
    assert stats["message_count"] == 0
