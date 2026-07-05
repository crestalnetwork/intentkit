from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from epyxid import XID
from sqlalchemy import delete, desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.agent.db import AgentTable
from intentkit.models.autonomous import (
    AutonomousCreateRequest,
    AutonomousExecution,
    AutonomousExecutionStatus,
    AutonomousExecutionTable,
    AutonomousTask,
    AutonomousTaskStatus,
    AutonomousTaskTable,
    AutonomousUpdateRequest,
    validate_cron_schedule,
)
from intentkit.models.chat import ChatMessage, ChatMessageTable
from intentkit.utils.error import IntentKitAPIError

# A running execution older than this is considered orphaned by a crashed
# process and gets marked as interrupted; a younger one blocks new runs.
EXECUTION_STALE_MINUTES = 30


def _task_not_found_error(task_id: str) -> IntentKitAPIError:
    return IntentKitAPIError(
        404,
        "TaskNotFound",
        f"Autonomous task with ID {task_id} not found.",
    )


def _execution_not_found_error(execution_id: str) -> IntentKitAPIError:
    return IntentKitAPIError(
        404,
        "ExecutionNotFound",
        f"Autonomous execution with ID {execution_id} not found.",
    )


def _invalid_target_agent_error(agent_id: str) -> IntentKitAPIError:
    return IntentKitAPIError(
        400,
        "InvalidTargetAgent",
        f"Target agent {agent_id} is not an active agent of this team.",
    )


async def _validate_target_agent(
    session: AsyncSession, team_id: str, agent_id: str
) -> None:
    """Ensure the target agent exists, belongs to the team, and is not archived."""
    agent = await session.get(AgentTable, agent_id)
    if agent is None or agent.team_id != team_id or agent.archived_at is not None:
        raise _invalid_target_agent_error(agent_id)


def _to_row(task: AutonomousTask) -> AutonomousTaskTable:
    return AutonomousTaskTable(
        id=task.id,
        team_id=task.team_id,
        target_agent_id=task.target_agent_id,
        created_by=task.created_by,
        name=task.name,
        description=task.description,
        cron=task.cron,
        prompt=task.prompt,
        enabled=task.enabled,
        status=task.status.value if task.status else None,
        next_run_time=task.next_run_time,
    )


async def list_team_autonomous_tasks(team_id: str) -> list[AutonomousTask]:
    """List all autonomous tasks owned by a team, oldest first."""
    async with get_session() as session:
        rows = await session.scalars(
            select(AutonomousTaskTable)
            .where(AutonomousTaskTable.team_id == team_id)
            .order_by(AutonomousTaskTable.created_at)
        )
        return [AutonomousTask.model_validate(row) for row in rows]


async def get_autonomous_task(team_id: str, task_id: str) -> AutonomousTask:
    """Get a single autonomous task, verifying it belongs to the team."""
    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)
        return AutonomousTask.model_validate(row)


async def add_autonomous_task(
    team_id: str,
    task_request: AutonomousCreateRequest,
    created_by: str | None = None,
) -> AutonomousTask:
    """Create a new autonomous task for a team.

    ``created_by`` is the user the task is attributed to (the authenticated
    caller); it is never taken from the request body.
    """
    validate_cron_schedule(task_request.cron)

    async with get_session() as session:
        if task_request.target_agent_id:
            await _validate_target_agent(session, team_id, task_request.target_agent_id)

        task = AutonomousTask(
            id=str(XID()),
            team_id=team_id,
            target_agent_id=task_request.target_agent_id,
            created_by=created_by,
            cron=task_request.cron,
            prompt=task_request.prompt,
            name=task_request.name,
            description=task_request.description,
            enabled=task_request.enabled,
        ).normalize_status_defaults()

        row = _to_row(task)
        session.add(row)
        await session.commit()
        # Reload so server-generated created_at/updated_at are returned (and to
        # avoid touching expired attributes after commit).
        await session.refresh(row)
        return AutonomousTask.model_validate(row)


async def update_autonomous_task(
    team_id: str, task_id: str, task_update: AutonomousUpdateRequest
) -> AutonomousTask:
    """Update fields of an existing autonomous task."""
    update_data = task_update.model_dump(exclude_unset=True)

    if update_data.get("cron") is not None:
        validate_cron_schedule(update_data["cron"])

    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)

        if update_data.get("target_agent_id"):
            await _validate_target_agent(
                session, team_id, update_data["target_agent_id"]
            )

        merged = (
            AutonomousTask.model_validate(row)
            .model_copy(update=update_data)
            .normalize_status_defaults()
        )

        row.target_agent_id = merged.target_agent_id
        row.name = merged.name
        row.description = merged.description
        row.cron = merged.cron
        row.prompt = merged.prompt
        row.enabled = merged.enabled
        row.status = merged.status.value if merged.status else None
        row.next_run_time = merged.next_run_time

        await session.commit()
        await session.refresh(row)
        return AutonomousTask.model_validate(row)


async def delete_autonomous_task(team_id: str, task_id: str) -> None:
    """Delete an autonomous task owned by the team, with its execution history."""
    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)
        _ = await session.execute(
            delete(AutonomousExecutionTable).where(
                AutonomousExecutionTable.task_id == task_id
            )
        )
        await session.delete(row)
        await session.commit()


async def update_autonomous_task_status(
    team_id: str,
    task_id: str,
    status: AutonomousTaskStatus | None,
    next_run_time: datetime | None,
) -> AutonomousTask:
    """Update only the runtime status/next_run_time of a task (single-row write).

    A disabled task always has its runtime state cleared, regardless of the
    requested status, so callers don't need to special-case it.
    """
    async with get_session() as session:
        row = await session.get(AutonomousTaskTable, task_id)
        if row is None or row.team_id != team_id:
            raise _task_not_found_error(task_id)

        if not row.enabled:
            status = None
            next_run_time = None

        row.status = status.value if status else None
        row.next_run_time = next_run_time
        # Snapshot before commit: expire_on_commit would expire row attributes,
        # and re-reading them after commit triggers an async lazy-load error.
        result = AutonomousTask.model_validate(row)
        await session.commit()
        return result


def _execution_to_row(execution: AutonomousExecution) -> AutonomousExecutionTable:
    # started_at is intentionally omitted so the server default applies.
    return AutonomousExecutionTable(
        id=execution.id,
        task_id=execution.task_id,
        team_id=execution.team_id,
        agent_id=execution.agent_id,
        target_agent_id=execution.target_agent_id,
        chat_id=execution.chat_id,
        message_id=execution.message_id,
        trigger=execution.trigger.value,
        triggered_by=execution.triggered_by,
        status=execution.status.value,
        error=execution.error,
        result=execution.result,
        input_tokens=execution.input_tokens,
        output_tokens=execution.output_tokens,
        cached_input_tokens=execution.cached_input_tokens,
        credit_cost=execution.credit_cost,
        message_count=execution.message_count,
        cold_start_cost=execution.cold_start_cost,
        finished_at=execution.finished_at,
    )


async def claim_autonomous_execution(
    execution: AutonomousExecution,
) -> AutonomousExecution | None:
    """Atomically claim a task's run slot by inserting its running execution.

    Returns None when another run of the task is already in progress, in which
    case the caller should skip this run. Running executions older than the
    staleness window (orphaned by a crashed process) are marked interrupted in
    the same transaction. The partial unique index on running executions makes
    the claim race-free: concurrent claims collide on insert and the loser
    gets None.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=EXECUTION_STALE_MINUTES)
    async with get_session() as session:
        rows = list(
            await session.scalars(
                select(AutonomousExecutionTable).where(
                    AutonomousExecutionTable.task_id == execution.task_id,
                    AutonomousExecutionTable.status
                    == AutonomousExecutionStatus.RUNNING.value,
                )
            )
        )
        if any(row.started_at and row.started_at > cutoff for row in rows):
            return None
        for row in rows:
            row.status = AutonomousExecutionStatus.ERROR.value
            row.error = "interrupted"
            row.finished_at = now
        if rows:
            # Flush the interrupts first so the unique running slot is free
            # before the new row is inserted (still one transaction).
            await session.flush()

        new_row = _execution_to_row(execution)
        session.add(new_row)
        try:
            await session.commit()
        except IntegrityError:
            # Another run claimed the slot between our check and the insert.
            await session.rollback()
            return None
        # Reload so the server-generated started_at is returned.
        await session.refresh(new_row)
        return AutonomousExecution.model_validate(new_row)


async def finish_autonomous_execution(
    execution_id: str,
    status: AutonomousExecutionStatus,
    *,
    error: str | None = None,
    result: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    credit_cost: Decimal | None = None,
    message_count: int = 0,
    cold_start_cost: float = 0.0,
) -> AutonomousExecution | None:
    """Finalize an execution record with its outcome and aggregated stats.

    Returns None when the execution row no longer exists (e.g. the task and
    its history were deleted while the run was in flight).
    """
    async with get_session() as session:
        row = await session.get(AutonomousExecutionTable, execution_id)
        if row is None:
            return None
        row.status = status.value
        row.error = error
        row.result = result
        row.input_tokens = input_tokens
        row.output_tokens = output_tokens
        row.cached_input_tokens = cached_input_tokens
        row.credit_cost = credit_cost
        row.message_count = message_count
        row.cold_start_cost = cold_start_cost
        row.finished_at = datetime.now(UTC)
        # Snapshot before commit (see update_autonomous_task_status).
        snapshot = AutonomousExecution.model_validate(row)
        await session.commit()
        return snapshot


async def get_fresh_running_execution(task_id: str) -> AutonomousExecution | None:
    """Return the latest running execution within the staleness window, if any.

    Used as a read-only pre-check before triggering a manual run.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=EXECUTION_STALE_MINUTES)
    async with get_session() as session:
        row = await session.scalar(
            select(AutonomousExecutionTable)
            .where(
                AutonomousExecutionTable.task_id == task_id,
                AutonomousExecutionTable.status
                == AutonomousExecutionStatus.RUNNING.value,
                AutonomousExecutionTable.started_at > cutoff,
            )
            .order_by(desc(AutonomousExecutionTable.id))
            .limit(1)
        )
        return AutonomousExecution.model_validate(row) if row else None


async def list_autonomous_executions(
    team_id: str,
    task_id: str,
    *,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[AutonomousExecution], bool, str | None]:
    """List executions of a task, newest first, with cursor pagination.

    Returns (executions, has_more, next_cursor). The cursor is an execution id
    (XIDs are time-ordered).
    """
    async with get_session() as session:
        task_row = await session.get(AutonomousTaskTable, task_id)
        if task_row is None or task_row.team_id != team_id:
            raise _task_not_found_error(task_id)

        stmt = (
            select(AutonomousExecutionTable)
            .where(AutonomousExecutionTable.task_id == task_id)
            .order_by(desc(AutonomousExecutionTable.id))
            .limit(limit + 1)
        )
        if cursor:
            stmt = stmt.where(AutonomousExecutionTable.id < cursor)
        rows = list(await session.scalars(stmt))
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = rows[-1].id if has_more and rows else None
        return (
            [AutonomousExecution.model_validate(row) for row in rows],
            has_more,
            next_cursor,
        )


async def get_autonomous_execution_messages(
    team_id: str, task_id: str, execution_id: str
) -> list[ChatMessage]:
    """Return the log of one execution: its trigger message and all replies.

    The trigger message's reply_to points to itself, so a single reply_to
    filter returns the complete, ordered log of exactly this run.
    """
    async with get_session() as session:
        task_row = await session.get(AutonomousTaskTable, task_id)
        if task_row is None or task_row.team_id != team_id:
            raise _task_not_found_error(task_id)

        execution = await session.get(AutonomousExecutionTable, execution_id)
        if execution is None or execution.task_id != task_id:
            raise _execution_not_found_error(execution_id)

        rows = await session.scalars(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.chat_id == execution.chat_id,
                ChatMessageTable.reply_to == execution.message_id,
            )
            .order_by(ChatMessageTable.id)
        )
        return [ChatMessage.model_validate(row) for row in rows]
