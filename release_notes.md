# Release v0.17.59

## Bug Fixes

- Fixed an issue where images sent through WeChat could be stored incorrectly and cause the AI to reject them, with the error then blocking any further messages in the same conversation. Inbound images are now validated before being forwarded to the AI, and unrecognized or unsupported formats are dropped cleanly instead of poisoning the conversation.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.58...v0.17.59
