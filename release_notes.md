# Release v2.19.0

## New Features

- **Memory page**: a new "Memory" entry in the account area shows what your agents remember, split into Team Memory (shared with the whole team) and Your Memory (what each agent remembers about you personally). Entries are shown truncated — open one to read the full text rendered as Markdown, or edit it directly. Memories are managed automatically by your agents, so you normally don't need to read or change them. Available in both the bundled frontend and the team frontend.
- **Memory API**: new endpoints to list and edit these memory documents (`/teams/{team_id}/memories` in the Team API, `/memories` in the local API), with size limits and per-user access control.

## Improvements

- **Long-term memory is always on**: memory now belongs to the conversation (team, user, channel, or cron task), not the agent, so the per-agent "Long-Term Memory" switch is gone. Agents skip the memory tool automatically in the few situations where it cannot work (sub-agent runs and anonymous visitors).
- **Super mode removed**: every agent now runs with the higher execution step limit by default, so the per-agent "Super Mode" switch and badge are gone. The limit can still be tuned server-wide.
- The lead agent's memory page entry shows the lead's real configured name and avatar.
- Fixed minor issues in prompt assembly and memory loading performance.
