# Release v2.34.1

## Improvements

- Routine dependency maintenance across the whole platform: the AI provider SDKs, web framework, database drivers, management frontend, and messaging integrations were all brought up to their latest releases.

## Bug Fixes

- Fixed bugs in the agent engine's error handling that surfaced with the latest OpenAI SDK update: brief network interruptions are reliably retried again, and requests that run out of time are now reported as timeouts instead of a generic internal error.
