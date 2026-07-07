# Release v2.12.0

## New Features

- Agents now narrate their tool use. Every tool call carries a short status line written by the agent in the user's own language — for example "Searching the web for the latest BTC news" — and the chat shows that line instead of the raw tool name. Expanding a tool call still reveals the tool name, parameters, and response for troubleshooting.
- Telegram and WeChat conversations benefit too: the "Running tool..." notice now shows the agent's own description of what it is doing, and when several tools run at once, each one gets its own line.

## Improvements

- Older messages and tools without a status line keep the previous display, so existing conversations look the same as before.
