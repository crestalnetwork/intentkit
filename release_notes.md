# Release v2.9.0

## New Features

- Scoped long-term memory: an agent now keeps separate memory documents for the team using it, for each individual user it talks to, for each channel thread (Telegram, Slack, Lark, WeChat), and for each scheduled task — all maintained through a single memory tool. When different teams talk to the same public agent, each team's memory stays completely private to them.
- Team wallet management: wallets can now be renamed and deleted, and Safe wallets' token spending limits adjusted, through new admin APIs. Deleting a team's last wallet is refused while agents still have on-chain tools configured, so an agent can never be left stranded.
- Guests talking to a published agent now get its full read-side abilities — recent posts and activities, sub-agent delegation, on-chain data lookups, and personal memory — while publishing content, signing transactions, and anything else that acts with the agent's identity stays strictly reserved for the owning team, enforced both when tools are offered and again when they execute.
- Publishing rules now keep delegation consistent: an agent can only be published when every sub-agent it uses is public too, and an agent that a public agent depends on cannot be hidden, archived, or deleted while the reference stands.

## Improvements

- Scheduled (autonomous) tasks no longer carry conversation history between runs. Every run starts fresh — dramatically cutting token costs for long-lived tasks — and tasks record the facts they need across runs in their own task memory instead.
- All costs incurred by delegated sub-agent work are billed to the account that started the conversation, no matter how deep the delegation chain goes.
- The tool catalog is now derived directly from the code instead of separate schema files, so tool pickers, validation, and the agent's own tool listing can never drift apart; toolsets that need a team wallet are now correctly hidden for teams without one.
- Fixed bugs in the tool availability and agent visibility modules.
