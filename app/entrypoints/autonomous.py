import logging
from decimal import Decimal
from typing import Any

from epyxid import XID

from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.autonomous import (
    claim_autonomous_execution,
    finish_autonomous_execution,
)
from intentkit.core.chat import clear_thread_memory
from intentkit.core.client import execute_agent, execute_lead
from intentkit.models.agent_activity import AgentActivityCreate
from intentkit.models.autonomous import (
    AutonomousExecution,
    AutonomousExecutionStatus,
    AutonomousExecutionTrigger,
)
from intentkit.models.chat import (
    AUTONOMOUS_CHAT_PREFIX,
    AuthorType,
    ChatMessage,
    ChatMessageCreate,
)

logger = logging.getLogger(__name__)

# Final agent reply is truncated to this length on the execution record.
EXECUTION_RESULT_MAX_LENGTH = 500


def aggregate_run_stats(resp: list[ChatMessage]) -> dict[str, Any]:
    """Aggregate one run's response messages into execution stats.

    Credit cost sums the message-level LLM costs and the per-tool-call costs,
    which are recorded as separate credit events.
    """
    credit_total = Decimal(0)
    for m in resp:
        if m.credit_cost:
            credit_total += m.credit_cost
        for call in m.tool_calls or []:
            cost = call.get("credit_cost")
            if cost:
                credit_total += Decimal(str(cost))

    result_text: str | None = None
    for m in reversed(resp):
        if m.author_type == AuthorType.AGENT and m.message:
            result_text = m.message[:EXECUTION_RESULT_MAX_LENGTH]
            break

    return {
        "input_tokens": sum(m.input_tokens for m in resp),
        "output_tokens": sum(m.output_tokens for m in resp),
        "cached_input_tokens": sum(m.cached_input_tokens for m in resp),
        "credit_cost": credit_total if credit_total else None,
        "message_count": len(resp),
        "cold_start_cost": next(
            (m.cold_start_cost for m in resp if m.cold_start_cost), 0.0
        ),
        "result": result_text,
    }


async def _finish_execution(
    execution: AutonomousExecution | None,
    resp: list[ChatMessage],
    error: str | None,
) -> None:
    """Best-effort finalization of the execution record."""
    if execution is None:
        return
    status = (
        AutonomousExecutionStatus.ERROR if error else AutonomousExecutionStatus.SUCCESS
    )
    try:
        _ = await finish_autonomous_execution(
            execution.id, status, error=error, **aggregate_run_stats(resp)
        )
    except Exception as e:
        logger.warning("Failed to finalize execution %s: %s", execution.id, e)


async def _record_error_activity(
    task_id: str,
    agent_id: str,
    text: str,
) -> None:
    """Best-effort surfacing of a run error as an agent activity."""
    try:
        _ = await create_agent_activity(
            AgentActivityCreate(
                agent_id=agent_id,
                text=text,
            )
        )
    except Exception as e:
        logger.warning(
            f"Failed to create error activity for task {task_id}: {e}",
            extra={"aid": agent_id},
        )


async def run_autonomous_task(
    team_id: str,
    owner_user_id: str,
    task_id: str,
    prompt: str,
    has_memory: bool = True,
    target_agent_id: str | None = None,
    trigger: AutonomousExecutionTrigger = AutonomousExecutionTrigger.CRON,
    triggered_by: str | None = None,
):
    """
    Run a team autonomous task.

    When ``target_agent_id`` is set, the task runs directly on that agent. When
    it is omitted, the task runs through the team lead, which decides delegation
    from the prompt.

    Each run is recorded as an :class:`AutonomousExecution`; the run's chat
    messages form its log. Overlapping runs of the same task are skipped, and
    running executions orphaned by a crash are marked interrupted.

    Args:
        team_id: The team that owns the task.
        owner_user_id: The user the run is attributed to (the team owner for
            cron runs, the requesting member for manual runs).
        task_id: The ID of the autonomous task.
        prompt: The autonomous prompt to execute.
        has_memory: Whether to retain conversation memory between runs. If False,
            clears thread memory before execution.
        target_agent_id: Optional agent to run directly; lead-orchestrated if None.
        trigger: How this run was triggered (cron or manual).
        triggered_by: User who triggered a manual run; None for cron runs.
    """
    via = f"agent {target_agent_id}" if target_agent_id else f"lead of team {team_id}"
    logger.info("Running autonomous task %s via %s", task_id, via)

    # The agent the run (and any error activity) is attributed to.
    effective_agent_id = target_agent_id or f"team-{team_id}"
    chat_id = f"{AUTONOMOUS_CHAT_PREFIX}{task_id}"

    message = ChatMessageCreate(
        id=str(XID()),
        agent_id=effective_agent_id,
        team_id=team_id,
        chat_id=chat_id,
        user_id=owner_user_id,
        author_id="autonomous",
        author_type=AuthorType.TRIGGER,
        thread_type=AuthorType.TRIGGER,
        message=prompt,
    )

    execution: AutonomousExecution | None = None
    try:
        execution = await claim_autonomous_execution(
            AutonomousExecution(
                id=str(XID()),
                task_id=task_id,
                team_id=team_id,
                agent_id=effective_agent_id,
                target_agent_id=target_agent_id,
                chat_id=chat_id,
                message_id=message.id,
                trigger=trigger,
                triggered_by=triggered_by,
            )
        )
        if execution is None:
            logger.warning(
                "Task %s skipped: a previous run is still in progress", task_id
            )
            return
    except Exception as e:
        # Never let execution bookkeeping block the run itself.
        logger.warning("Failed to record execution for task %s: %s", task_id, e)

    try:
        # Clear thread memory if has_memory is False
        if not has_memory:
            try:
                _ = await clear_thread_memory(effective_agent_id, chat_id)
                logger.debug(
                    f"Cleared thread memory for task {task_id} (has_memory=False)"
                )
            except Exception as e:
                # Log the error but continue with execution
                logger.warning(
                    "Failed to clear thread memory for task %s: %s", task_id, e
                )

        resp: list[ChatMessage]
        if target_agent_id:
            # Direct execution on the target agent.
            resp = await execute_agent(message)
        else:
            # Lead-orchestrated execution: the lead reads the prompt and
            # delegates to a team agent via lead_call_agent.
            resp = await execute_lead(team_id, owner_user_id, message)

        # Log the response
        logger.info(
            f"Task {task_id} completed: " + "\n".join(str(m) for m in resp),
            extra={"aid": effective_agent_id},
        )

        # Classify the outcome from the last response message.
        error_text: str | None = None
        if not resp:
            error_text = "Unexpected result: empty response"
        else:
            last_msg = resp[-1]
            if last_msg.author_type == AuthorType.AGENT:
                pass  # Success
            elif last_msg.author_type == AuthorType.SYSTEM:
                error_text = f"Task execution error: {last_msg.message}"
            else:
                error_text = "Unexpected return error"

        await _finish_execution(execution, resp, error_text)

        if error_text:
            await _record_error_activity(task_id, effective_agent_id, error_text)

    except Exception as e:
        logger.error(
            f"Error in autonomous task {task_id} for team {team_id}: {repr(e)}",
            exc_info=True,
        )
        error_text = f"Autonomous task exception: {repr(e)}"
        await _finish_execution(execution, [], error_text)
        await _record_error_activity(task_id, effective_agent_id, error_text)
