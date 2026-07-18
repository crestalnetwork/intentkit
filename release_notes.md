# Release v2.29.0

## Improvements

- Simplified the agent lifecycle: creating or updating an agent simply takes effect immediately. The leftover "deploy" wording from an older draft-based workflow is gone from agent tools, messages, and notifications, so assistants describe changes the way they actually work.
- An agent's "last updated" time now reflects real edits only — routine background refreshes such as hourly account snapshots and asset caches no longer count. This keeps the Team Lead's view of recently active agents meaningful and avoids unnecessary periodic reinitialization of busy agents.
- Internal cleanup of legacy code and a leftover database column from the retired draft system; the database schema updates itself automatically on upgrade.
