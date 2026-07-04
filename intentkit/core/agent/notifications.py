from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.utils.alert import send_alert


def send_agent_notification(agent: Agent, agent_data: AgentData, message: str) -> None:
    """Send a notification about agent creation or update.

    Args:
        agent: The agent that was created or updated
        agent_data: The agent data to update
        message: The notification message
    """
    tools_formatted = ""
    if agent.tools:
        enabled_categories = []
        for category, tool_config in agent.tools.items():
            if tool_config and tool_config.get("enabled") is True:
                tools_list = []
                states = tool_config.get("states", {})
                public_tools = [
                    tool for tool, state in states.items() if state == "public"
                ]
                private_tools = [
                    tool for tool, state in states.items() if state == "private"
                ]

                if public_tools:
                    tools_list.append(f"  Public: {', '.join(public_tools)}")
                if private_tools:
                    tools_list.append(f"  Private: {', '.join(private_tools)}")

                if tools_list:
                    enabled_categories.append(
                        f"• {category}:\n{chr(10).join(tools_list)}"
                    )

        if enabled_categories:
            tools_formatted = "\n".join(enabled_categories)
        else:
            tools_formatted = "No enabled tools"
    else:
        tools_formatted = "None"

    send_alert(
        message,
        attachments=[
            {
                "color": "good",
                "fields": [
                    {"title": "ID", "short": True, "value": agent.id},
                    {"title": "Name", "short": True, "value": agent.name},
                    {"title": "Model", "short": True, "value": agent.model},
                    {
                        "title": "Network",
                        "short": True,
                        "value": agent.network_id or "Not Set",
                    },
                    {
                        "title": "Telegram Enabled",
                        "short": True,
                        "value": str(agent.telegram_entrypoint_enabled),
                    },
                    {
                        "title": "Telegram Username",
                        "short": True,
                        "value": agent_data.telegram_username,
                    },
                    {
                        "title": "Wallet ID",
                        "value": agent.wallet_id or "None",
                    },
                    {
                        "title": "Tools",
                        "value": tools_formatted,
                    },
                ],
            }
        ],
    )
