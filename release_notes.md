# Release v2.20.0

## New Features

- **Task planning rebuilt**: agents with the todo feature enabled now reliably maintain a working plan for complex, multi-step requests. Plans stay accurate through very long conversations (the agent no longer loses sight of its list when older context is compacted away), a finished task's list is cleaned up automatically so it never leaks into the next request, and prompt-cache efficiency is preserved throughout.
- **Visible plans everywhere**: web chat renders the plan as a live checklist with per-step states and a progress count. IM channels (Telegram, WeChat, Slack, Lark) show the checklist when a plan is created and a compact one-line progress note as steps complete.

## Improvements

- Fixed bugs in the todo module that could leave the planning tool entirely unavailable to the agent.
- Sub-agent runs no longer carry their own todo lists — planning stays with the agent you are talking to. Scheduled (cron) runs keep full planning support.
