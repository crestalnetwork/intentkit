# Release v2.7.0

## New Features

- Links: teams can now connect external app accounts — Twitter/X, Notion, Gmail, and Supabase — and the team lead agent gains the ability to act through them: read and send email, post to X, work with Notion pages, manage Supabase projects, and more. Connecting an account is always a standard OAuth authorization (users never copy API keys), accounts can be unlinked at any time, and when someone asks about an app that isn't linked yet, the lead points them to the Links page. Available in both the team API and the local single-user deployment.
- Channels: Slack and Lark/Feishu join the team channel lineup — a team admin authorizes the official app into their own workspace with a single click. Telegram now runs through one official shared bot that groups join via a bind link, so teams no longer manage their own bot tokens.

## Improvements

- Database schema changes are now managed with Alembic migrations, making upgrades safer and more repeatable.
- Release builds now ship ready-to-run images for the Lark and Slack channel services.
