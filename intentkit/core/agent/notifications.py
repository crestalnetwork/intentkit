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
    autonomous_formatted = ""
    if agent.autonomous:
        enabled_autonomous = [auto for auto in agent.autonomous if auto.enabled]
        if enabled_autonomous:
            autonomous_items = []
            for auto in enabled_autonomous:
                schedule = (
                    f"cron: {auto.cron}" if auto.cron else f"minutes: {auto.minutes}"
                )
                autonomous_items.append(
                    f"• {auto.id}: {auto.name or 'Unnamed'} ({schedule})"
                )
            autonomous_formatted = "\n".join(autonomous_items)
        else:
            autonomous_formatted = "No enabled autonomous configurations"
    else:
        autonomous_formatted = "None"

    skills_formatted = ""
    if agent.skills:
        enabled_categories = []
        for category, skill_config in agent.skills.items():
            if skill_config and skill_config.get("enabled") is True:
                skills_list = []
                states = skill_config.get("states", {})
                public_skills = [
                    skill for skill, state in states.items() if state == "public"
                ]
                private_skills = [
                    skill for skill, state in states.items() if state == "private"
                ]

                if public_skills:
                    skills_list.append(f"  Public: {', '.join(public_skills)}")
                if private_skills:
                    skills_list.append(f"  Private: {', '.join(private_skills)}")

                if skills_list:
                    enabled_categories.append(
                        f"• {category}:\n{chr(10).join(skills_list)}"
                    )

        if enabled_categories:
            skills_formatted = "\n".join(enabled_categories)
        else:
            skills_formatted = "No enabled skills"
    else:
        skills_formatted = "None"

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
                        "title": "X Username",
                        "short": True,
                        "value": agent_data.twitter_username,
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
                        "title": "Wallet Address",
                        "value": agent_data.evm_wallet_address,
                    },
                    {
                        "title": "Autonomous",
                        "value": autonomous_formatted,
                    },
                    {
                        "title": "Skills",
                        "value": skills_formatted,
                    },
                ],
            }
        ],
    )
