## New Features

### Telegram Channel Verification System
- Team Telegram channels now require verification before chats can interact with the bot. When a bot is connected, a 4-digit verification code is generated. New private chats or group conversations must send this code to activate. The code automatically regenerates after each successful verification for security.

### Telegram Bot Status Monitoring
- The Channels page now shows real-time bot listening status (Listening / Connecting / Error), bot username, and a list of all verified chats. Admins can remove verified chats directly from the UI.

### Verification Rate Limiting
- To prevent brute-force attempts, verification is limited to 3 attempts per chat within a 10-minute window.

## Improvements
- Minor gitignore improvements.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.1...v0.17.2
