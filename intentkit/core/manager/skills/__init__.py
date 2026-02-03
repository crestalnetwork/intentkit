"""Manager skills package."""

from intentkit.core.manager.skills.add_autonomous_task import (
    AddAutonomousTask,
    add_autonomous_task_skill,
)
from intentkit.core.manager.skills.delete_autonomous_task import (
    DeleteAutonomousTask,
    delete_autonomous_task_skill,
)
from intentkit.core.manager.skills.draft import (
    GetAgentLatestDraftSkill,
    UpdateAgentDraftSkill,
    get_agent_latest_draft_skill,
    update_agent_draft_skill,
)
from intentkit.core.manager.skills.edit_autonomous_task import (
    EditAutonomousTask,
    edit_autonomous_task_skill,
)
from intentkit.core.manager.skills.list_autonomous_tasks import (
    ListAutonomousTasks,
    list_autonomous_tasks_skill,
)
from intentkit.core.manager.skills.llm import (
    GetAvailableLLMs,
    get_available_llms_skill,
)
from intentkit.core.manager.skills.public_info import (
    GetAgentLatestPublicInfoSkill,
    UpdatePublicInfoSkill,
    get_agent_latest_public_info_skill,
    update_public_info_skill,
)
from intentkit.core.manager.skills.read_agent_api_key import (
    ReadAgentApiKey,
    read_agent_api_key_skill,
)
from intentkit.core.manager.skills.regenerate_agent_api_key import (
    RegenerateAgentApiKey,
    regenerate_agent_api_key_skill,
)
from intentkit.skills.base import NoArgsSchema

__all__ = [
    "NoArgsSchema",
    "GetAgentLatestDraftSkill",
    "UpdateAgentDraftSkill",
    "get_agent_latest_draft_skill",
    "update_agent_draft_skill",
    "GetAgentLatestPublicInfoSkill",
    "UpdatePublicInfoSkill",
    "get_agent_latest_public_info_skill",
    "update_public_info_skill",
    "AddAutonomousTask",
    "add_autonomous_task_skill",
    "DeleteAutonomousTask",
    "delete_autonomous_task_skill",
    "EditAutonomousTask",
    "edit_autonomous_task_skill",
    "ListAutonomousTasks",
    "list_autonomous_tasks_skill",
    "GetAvailableLLMs",
    "get_available_llms_skill",
    "ReadAgentApiKey",
    "read_agent_api_key_skill",
    "RegenerateAgentApiKey",
    "regenerate_agent_api_key_skill",
]
