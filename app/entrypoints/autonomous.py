import logging

from epyxid import XID

from app.core.engine import execute_agent
from models.chat import AuthorType, ChatMessageCreate

logger = logging.getLogger(__name__)


async def run_autonomous_task(
    agent_id: str, agent_owner: str, task_id: str, prompt: str
):
    """
    Run a specific autonomous task for an agent.

    Args:
        agent_id: The ID of the agent
        task_id: The ID of the autonomous task
        prompt: The autonomous prompt to execute
    """
    logger.info(f"Running autonomous task {task_id} for agent {agent_id}")

    try:
        # Run the autonomous action
        chat_id = f"autonomous-{task_id}"
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
    except Exception as e:
        logger.error(
            f"Error in autonomous task {task_id} for agent {agent_id}: {str(e)}"
        )
