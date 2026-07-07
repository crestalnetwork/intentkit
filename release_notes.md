# Release v2.13.0

## New Features

- Tool calls now report their status the moment they start. The chat stream sends a live frame as soon as the agent begins a tool call, so the web UI shows the agent's status line with a spinner right away — expanding a running call reveals its request parameters, and when the call finishes, the result folds into the same badge.
- Telegram, WeChat, Slack, and Lark conversations get the status message at the start of the tool call instead of after it finished, so users see what the agent is doing while it works.

## Improvements

- Cancelled or interrupted conversations clean up their leftover "running" indicators automatically, and conversation history stays exactly as before — the live frames are never stored.
- Fixed small inconsistencies in how non-streaming API responses assembled their message lists.
