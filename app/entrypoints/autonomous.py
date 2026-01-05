import logging

from epyxid import XID

from intentkit.core.agent_activity import create_agent_activity
from intentkit.core.chat import clear_thread_memory
from intentkit.core.client import execute_agent
from intentkit.models.agent_activity import AgentActivityCreate
from intentkit.models.chat import AuthorType, ChatMessageCreate

logger = logging.getLogger(__name__)


async def run_autonomous_task(
    agent_id: str,
    agent_owner: str,
    task_id: str,
    prompt: str,
    has_memory: bool = True,
):
    """
    Run a specific autonomous task for an agent.

    Args:
        agent_id: The ID of the agent
        agent_owner: The owner of the agent
        task_id: The ID of the autonomous task
        prompt: The autonomous prompt to execute
        has_memory: Whether to retain conversation memory between runs.
                   If False, clears thread memory before execution.
    """
    logger.info(f"Running autonomous task {task_id} for agent {agent_id}")

    try:
        # Run the autonomous action
        chat_id = f"autonomous-{task_id}"

        # Clear thread memory if has_memory is False
        if not has_memory:
            try:
                _ = await clear_thread_memory(agent_id, chat_id)
                logger.debug(
                    f"Cleared thread memory for task {task_id} (has_memory=False)"
                )
            except Exception as e:
                # Log the error but continue with execution
                logger.warning(f"Failed to clear thread memory for task {task_id}: {e}")
        message = ChatMessageCreate(
            id=str(XID()),
            agent_id=agent_id,
            chat_id=chat_id,
            user_id=agent_owner,
            author_id="autonomous",
            author_type=AuthorType.TRIGGER,
            thread_type=AuthorType.TRIGGER,
            message=prompt,
        )

        # Execute agent and get response
        resp = await execute_agent(message)

        # Log the response
        logger.info(
            f"Task {task_id} completed: " + "\n".join(str(m) for m in resp),
            extra={"aid": agent_id},
        )

        # Check response and create error activity if needed
        if not resp:
            try:
                activity = AgentActivityCreate(
                    agent_id=agent_id,
                    text="Unexpected result: empty response",
                )
                _ = await create_agent_activity(activity)
            except Exception as e:
                logger.warning(
                    f"Failed to create error activity for task {task_id}: {e}",
                    extra={"aid": agent_id},
                )
        else:
            last_msg = resp[-1]
            error_text = None

            if last_msg.author_type == AuthorType.AGENT:
                pass  # Success, do nothing
            elif last_msg.author_type == AuthorType.SYSTEM:
                error_text = f"Task execution error: {last_msg.message}"
            else:
                error_text = "Unexpected return error"

            if error_text:
                try:
                    activity = AgentActivityCreate(
                        agent_id=agent_id,
                        text=error_text,
                    )
                    _ = await create_agent_activity(activity)
                except Exception as e:
                    logger.warning(
                        f"Failed to create error activity for task {task_id}: {e}",
                        extra={"aid": agent_id},
                    )

    except Exception as e:
        logger.error(
            f"Error in autonomous task {task_id} for agent {agent_id}: {str(e)}"
        )
        try:
            activity = AgentActivityCreate(
                agent_id=agent_id,
                text=f"Autonomous task exception: {str(e)}",
            )
            _ = await create_agent_activity(activity)
        except Exception as activity_error:
            logger.warning(
                f"Failed to create exception activity for task {task_id}: {activity_error}",
                extra={"aid": agent_id},
            )
