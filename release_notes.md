# Release v2.6.6

## Bug Fixes

- Fixed a billing issue in agent-to-agent delegation: when an agent handed a task off to another agent, the cost of that delegated work was not charged back to the team paying for the conversation (and, with billing enabled, could even prevent the delegated task from running). Delegated work is now correctly billed to the caller's account.
