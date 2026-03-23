## New Features

- **Supabase Authentication & User Management**: Full Supabase-based authentication with user and team management, enabling secure multi-user access to team resources.
- **Standalone Team API**: Comprehensive team API with endpoints for agent management, core configuration, metadata, autonomous scheduling, content feeds, and chat — ready for frontend integration.
- **JWKS JWT Verification**: Team API now supports RS256 JWT verification via JWKS, with automatic key rotation support. Legacy HS256 signing key remains as a fallback.

## Improvements

- Improved team API structure with dedicated routers for core and metadata operations.
- Enhanced team membership and permission system.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.14.0...v0.15.0
