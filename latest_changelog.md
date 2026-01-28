### Fixes

- Made `payer` field in `X402Order` optional to support older records and cases where payer information is missing.
- Added unit tests for ensuring `X402Order` creation works without `payer` field.

[Full Changelog](https://github.com/crestalnetwork/intentkit/compare/v0.9.11...v0.9.12)