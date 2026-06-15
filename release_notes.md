# Release v2.6.4

## Improvements

- Observability traces (Langfuse) now show a readable name — the agent's name and its owning team — instead of the raw agent id, and carry richer filterable details: agent and team display names, the caller's team for public agents (with an external-caller flag), visibility, and tags. No user-facing changes.

## Bug Fixes

- Fixed the test suite still sending traces to the observability backend (Langfuse): the earlier fix was undone by environment reloading, so test/local data kept appearing. Tests now reliably emit nothing.
