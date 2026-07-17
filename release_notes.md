# Release v2.27.3

## Bug Fixes

- Fixed a crash on the agent chat page ("Failed to load agent") that could occur while an agent streamed several updates in quick succession, such as live tool-call status frames. The chat now stays stable through rapid bursts of activity.
- Follow-up messages in the same conversation now stream their replies live from the start; previously the beginning of a second reply could stay hidden until the response finished.
