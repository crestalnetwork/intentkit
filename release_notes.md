## New Features

### Team WeChat Integration
- **WeChat QR code login** is now available for team deployments. Team admins can connect a WeChat bot to their team's Lead agent through the channel management interface, using the same QR code scan flow available in the local version.

## Improvements
- Extracted shared code (health endpoint, metadata, chat helpers, autonomous helpers, WeChat helpers) from local API into a common module, reducing duplication between local and team API servers.
- Synchronized team Docker Compose configuration with latest changes.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.0...v0.17.1
