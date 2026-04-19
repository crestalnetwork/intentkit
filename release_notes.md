# Release v0.17.57

## New Features

- Added time-limited **share links** for chats and posts. Team members can now generate a public URL that lets anyone — including recipients without an account — view a chat transcript or post for three days.
- When posts are delivered to WeChat or Telegram, the push message now contains a share link instead of a login-gated URL, so off-platform recipients can open the content directly.

## Improvements

- Each public view increments a view counter on the share link, and creator metadata (user and team) is retained for future reporting.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.56...v0.17.57
