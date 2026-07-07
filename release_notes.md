# Release v2.10.0

## New Features

- Rich UI components (cards and clickable choice options) are now a built-in ability of every agent — nothing to enable in the tool picker anymore. Agents show them automatically wherever someone is actually watching the conversation: the web app, API clients, Telegram, WeChat, Lark, and Slack. Scheduled background runs and agent-to-agent delegation deliberately skip them, since there is no live user to click anything there.

## Improvements

- WeChat now displays card images as real pictures instead of dropping them; the rest of the card follows as text, which is the richest form WeChat's bot messaging supports.
- Existing agents that had the UI components selected keep working unchanged — old configurations are accepted and tidied up automatically.
