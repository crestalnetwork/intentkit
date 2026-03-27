## Improvements

- **Simplified Deployment**: Consolidated from three domains (API, App, CDN) to a single domain, reducing DNS and certificate setup complexity.
- **Basic Auth Support**: Added optional username/password authentication for the web UI, configurable via environment variables.
- **Updated Documentation**: Revised Docker Compose deployment guide to reflect the simplified setup.

## Bug Fixes

- Fixed an issue where the frontend could not reach the API in Docker deployments due to Next.js build-time environment variable limitations.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.16.0...v0.16.1
