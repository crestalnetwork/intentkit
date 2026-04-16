# Release v0.17.50

## New Features

- **WeChat image storage**: Images received from WeChat are now downloaded, decrypted, and stored on S3, providing stable URLs that the AI model can reliably access. Previously, WeChat's temporary CDN links could expire before the model processed them.

- **Cross-turn media forwarding**: The lead agent can now forward images, videos, and files to sub-agents even when the media was received in a previous message. Attachment URLs are made visible to the lead so it can reference them across conversation turns.

## Other

- Updated dependencies.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.49...v0.17.50
