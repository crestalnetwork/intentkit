## Bug Fixes

- Fixed an issue in the Privy client where transfers would fail if the Allowance Module was not enabled or used incorrectly. Now implements a smart fallback to use the Allowance Module if available, and direct owner transfer otherwise.

[Diff v0.9.1...v0.9.2](https://github.com/crestalnetwork/intentkit/compare/v0.9.1...v0.9.2)