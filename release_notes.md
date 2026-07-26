## Agent Form Rebuilt

The agent creation and editing form has been rebuilt. It used to be generated from a schema the backend served; it is now written directly in the web app. That removes a layer of indirection that made every form change a two-sided edit, and it lets the create page render immediately instead of waiting on the server.

**What you'll notice**

- Fields are grouped into **Basic**, **LLM** and **Tools** sections rather than one long list.
- Clearing a field while editing an agent — emptying the system prompt, deselecting every tool, or returning reasoning effort to the model default — now saves correctly. These previously reported success but kept the old value.
- The form no longer rejects names, slugs or prompts that the service actually accepts.

A new endpoint serves the tool catalogue to any client that needs to build a tool picker.

## Claude Opus 5

Agents can now run on **Claude Opus 5**, at the same price as Opus 4.8. Agents set to Opus 4.8 move over automatically and need no changes. Two long-standing errors in the Opus entry were also corrected — its maximum response length was understated by a wide margin, and file attachments were listed as unsupported when they work.

## Performance

- Startup is faster: agent definitions are now parsed with a native library, cutting that step from roughly 44ms to 2ms, and the work has been moved off the main request loop.
- Several operations that could briefly block the service during startup and shutdown no longer do.

## Maintenance

- Python dependencies refreshed across the board, including the Redis client's first major release in some time. Connection timeouts are now set explicitly so the upgrade changes no behaviour.
- Long-standing structural issues in the core module were resolved, restoring a clean bill of health from the project's static analysis and linting suite for the first time since mid-July.
- Log records now identify which tool produced them; previously every tool logged under a shared name.
- Fixed bugs in the activity notification, tool logging and agent configuration modules, and removed several pieces of dead code.
