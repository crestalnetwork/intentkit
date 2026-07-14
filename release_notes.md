# Release v2.24.0

## Improvements

- **Task planning is now built in for every agent**: the per-agent "todo" toggle is gone. All agents — including the team lead — plan complex multi-step requests automatically, while delegated sub-agent runs still skip planning (the plan belongs to the agent you are talking to).
- Removed the automatic tool picker that kicked in for agents with a very large tool list; agents now always work with their full set of tools directly.

## Notes for operators

- Predefined public agents will report a one-time "updated" during the next sync — their content fingerprint changed with the removed setting. No action needed.
