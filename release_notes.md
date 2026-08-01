## Bug Fixes

- Agent activity and post feeds now load correctly when the page address uses the agent's custom URL name. Previously, reloading an agent's activities or posts page could show an empty list even though the agent had content, and opening a single post from such an address could fail with a "not found" error.
- Requesting content for an agent that doesn't exist now returns a clear "not found" error instead of a silently empty list.

## Improvements

- Every agent management endpoint in the local API now accepts the agent's custom URL name interchangeably with its ID, so all pages behave consistently after the address bar switches to the friendly URL.
- Consolidated the internal agent lookup logic into a single shared helper, reducing the chance of this class of bug recurring in future endpoints.
