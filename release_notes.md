# Release v2.8.0

## New Features

- Agents now always know which channel a conversation originally came from (web, Telegram, WeChat, Lark, Slack, or a scheduled task), even when the work is delegated through one or more sub-agents. Channel-specific behavior such as formatting rules now applies correctly to delegated agents at any depth.
- Agents are now explicitly aware when they run as a sub-agent on behalf of another agent, and adjust their behavior accordingly — for example, sub-agents spawned by an autonomous task know they must complete the work without asking the user for input.

## Improvements

- Observability: traces are now labeled with the real entry channel instead of a generic internal marker, and delegated runs carry a dedicated sub-agent flag, making it much easier to filter and analyze multi-agent conversations.
- Chat history records for delegated runs are now consistently attributed to the originating channel.
