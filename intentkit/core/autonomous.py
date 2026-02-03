from __future__ import annotations

from typing import Any

from epyxid import XID
from sqlalchemy import select

from intentkit.config.db import get_session
from intentkit.models.agent.autonomous import (
    AgentAutonomous,
    AutonomousCreateRequest,
    AutonomousUpdateRequest,
)
from intentkit.models.agent.db import AgentTable
from intentkit.utils.error import IntentKitAPIError


def _deserialize_autonomous(
    autonomous_data: list[Any] | None,
) -> list[AgentAutonomous]:
    if not autonomous_data:
        return []

    deserialized: list[AgentAutonomous] = []
    for entry in autonomous_data:
        if isinstance(entry, AgentAutonomous):
            deserialized.append(entry)
        else:
            deserialized.append(AgentAutonomous.model_validate(entry))
    return deserialized


def _serialize_autonomous(tasks: list[AgentAutonomous]) -> list[dict[str, Any]]:
    return [task.model_dump(mode="json") for task in tasks]


def _autonomous_not_allowed_error() -> IntentKitAPIError:
    return IntentKitAPIError(
        400,
        "AgentNotDeployed",
        "Only deployed agents can call this feature.",
    )


def _agent_not_found_error(agent_id: str) -> IntentKitAPIError:
    return IntentKitAPIError(
        404,
        "AgentNotFound",
        f"Agent with ID {agent_id} not found.",
    )


async def list_autonomous_tasks(agent_id: str) -> list[AgentAutonomous]:
    async with get_session() as session:
        # Check if agent exists and get its autonomous storage and archived status
        result = await session.execute(
            select(AgentTable.autonomous, AgentTable.archived_at).where(
                AgentTable.id == agent_id
            )
        )
        row = result.first()

        if row is None:
            raise _agent_not_found_error(agent_id)

        autonomous_data, archived_at = row

        if archived_at is not None:
            raise _autonomous_not_allowed_error()

        return _deserialize_autonomous(autonomous_data)


async def add_autonomous_task(
    agent_id: str, task_request: AutonomousCreateRequest
) -> AgentAutonomous:
    async with get_session() as session:
        db_agent = await session.get(AgentTable, agent_id)
        if db_agent is None:
            raise _agent_not_found_error(agent_id)
        if db_agent.archived_at is not None:
            raise _autonomous_not_allowed_error()

        # Create new task model from request
        task = AgentAutonomous(
            id=str(XID()),
            cron=task_request.cron,
            prompt=task_request.prompt,
            name=task_request.name,
            description=task_request.description,
            enabled=task_request.enabled,
            has_memory=task_request.has_memory,
        )

        current_tasks = _deserialize_autonomous(db_agent.autonomous)
        normalized_task = task.normalize_status_defaults()
        current_tasks.append(normalized_task)

        db_agent.autonomous = _serialize_autonomous(current_tasks)
        await session.commit()

    return normalized_task


async def delete_autonomous_task(agent_id: str, task_id: str) -> None:
    async with get_session() as session:
        db_agent = await session.get(AgentTable, agent_id)
        if db_agent is None:
            raise _agent_not_found_error(agent_id)
        if db_agent.archived_at is not None:
            raise _autonomous_not_allowed_error()

        current_tasks = _deserialize_autonomous(db_agent.autonomous)

        updated_tasks = [task for task in current_tasks if task.id != task_id]
        if len(updated_tasks) == len(current_tasks):
            raise IntentKitAPIError(
                404,
                "TaskNotFound",
                f"Autonomous task with ID {task_id} not found.",
            )

        db_agent.autonomous = _serialize_autonomous(updated_tasks)
        await session.commit()


async def update_autonomous_task(
    agent_id: str, task_id: str, task_update: AutonomousUpdateRequest
) -> AgentAutonomous:
    async with get_session() as session:
        db_agent = await session.get(AgentTable, agent_id)
        if db_agent is None:
            raise _agent_not_found_error(agent_id)
        if db_agent.archived_at is not None:
            raise _autonomous_not_allowed_error()

        current_tasks = _deserialize_autonomous(db_agent.autonomous)

        updated_task: AgentAutonomous | None = None
        rewritten_tasks: list[AgentAutonomous] = []
        for task in current_tasks:
            if task.id == task_id:
                # Update only fields that are set in the request
                update_data = task_update.model_dump(exclude_unset=True)
                task_dict = task.model_dump()
                task_dict.update(update_data)

                updated_task = AgentAutonomous.model_validate(
                    task_dict
                ).normalize_status_defaults()
                rewritten_tasks.append(updated_task)
            else:
                rewritten_tasks.append(task)

        if updated_task is None:
            raise IntentKitAPIError(
                404,
                "TaskNotFound",
                f"Autonomous task with ID {task_id} not found.",
            )

        db_agent.autonomous = _serialize_autonomous(rewritten_tasks)
        await session.commit()

    return updated_task
