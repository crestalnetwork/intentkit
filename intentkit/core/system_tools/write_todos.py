"""System tool for managing the agent's todo list (task planning)."""

from typing import Annotated, Any, override

from langchain_core.messages import ToolMessage
from langchain_core.tools import ArgsSchema, InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import Todo
from intentkit.core.system_tools.base import SystemTool

# Prompt text ported from langchain's TodoListMiddleware (MIT), which this
# tool replaces. Keep the guidance aligned with it when upgrading langchain.
WRITE_TODOS_TOOL_DESCRIPTION = """Use this tool to create and manage a structured task list for your current work session. This helps you track progress and organize complex tasks.

Only use this tool if you think it will be helpful in staying organized. If the user's request is trivial and takes less than 3 steps, it is better to NOT use this tool and just do the task directly.

## When to Use This Tool

Use this tool in these scenarios:

1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. The plan may need future revisions or updates based on results from the first few steps

## How to Use This Tool

1. When you start working on a task - Mark it as in_progress BEFORE beginning work.
2. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation.
3. You can also update future tasks, such as deleting them if they are no longer necessary, or adding new tasks that are necessary. Don't change previously completed tasks.
4. You can make several updates to the todo list at once. For example, when you complete a task, you can mark the next task you need to start as in_progress.

## When NOT to Use This Tool

It is important to skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

## Task States and Management

1. **Task States**: Use these states to track progress:
    - pending: Task not yet started
    - in_progress: Currently working on (you can have multiple tasks in_progress at a time if they are not related to each other and can be run in parallel)
    - completed: Task finished successfully

2. **Task Management**:
    - Update task status in real-time as you work
    - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
    - Complete current tasks before starting new ones
    - Remove tasks that are no longer relevant from the list entirely
    - IMPORTANT: When you write this todo list, you should mark your first task (or tasks) as in_progress immediately!.
    - IMPORTANT: Unless all tasks are completed, you should always have at least one task in_progress.

3. **Task Completion Requirements**:
    - ONLY mark a task as completed when you have FULLY accomplished it
    - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
    - When blocked, create a new task describing what needs to be resolved
    - Never mark a task as completed if:
        - There are unresolved issues or errors
        - Work is partial or incomplete
        - You encountered blockers that prevent completion
        - You couldn't find necessary resources or dependencies
        - Quality standards haven't been met

4. **Task Breakdown**:
    - Create specific, actionable items
    - Break complex tasks into smaller, manageable steps
    - Use clear, descriptive task names
    - Write task content in the language the user is speaking

Being proactive with task management ensures you complete all requirements successfully
Remember: If you only need to make a few tool calls to complete a task, and it is clear what you need to do, it is better to just do the task directly and NOT call this tool at all.

## When You Finish

`write_todos` tracks your work; it does not deliver the answer. Whatever the user asked for — computations, summaries, comparisons, data — must appear as text content in a message after your final `write_todos` call. Marking the last todo complete is not itself an answer to the user."""

_STATUS_MARKERS = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}


def render_todos(todos: list[Todo]) -> str:
    """Render a todo list as a markdown checklist."""
    return "\n".join(
        f"- {_STATUS_MARKERS[todo['status']]} {todo['content']}" for todo in todos
    )


class WriteTodosInput(BaseModel):
    """Input schema for the `write_todos` tool."""

    todos: list[Todo] = Field(
        description=(
            "The full todo list. Each call replaces the previous list "
            "entirely, so always provide every remaining item."
        )
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


class WriteTodosTool(SystemTool):
    """Tool that replaces the conversation's todo list.

    The list lives in the graph state's ``todos`` channel (whole-list
    replacement). The ToolMessage echoes the rendered checklist — between
    compactions this echo is the model's only view of the list, so any
    context-trimming pass must leave these results intact.

    ``interactive_only``: planning is for a live user watching the checklist.
    Sub-agent runs plan in the calling agent, and cron runs are single-shot
    with no shared chat (they carry facts via task memory instead).
    """

    name: str = "write_todos"
    description: str = WRITE_TODOS_TOOL_DESCRIPTION
    args_schema: ArgsSchema | None = WriteTodosInput
    interactive_only: bool = True

    @override
    async def _arun(self, todos: list[Todo], tool_call_id: str) -> Command[Any]:
        if todos:
            content = f"Todo list updated:\n{render_todos(todos)}"
        else:
            content = "Todo list cleared."
        return Command(
            update={
                "todos": todos,
                "messages": [ToolMessage(content, tool_call_id=tool_call_id)],
            }
        )
