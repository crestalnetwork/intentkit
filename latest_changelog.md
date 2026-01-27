## v0.9.6

### Fixes

- Fixed `x402_order` table missing `payer` field, ensuring proper record of who paid.
- Fixed `pay_to` field being "unknown" in some x402 payment scenarios by capturing it from payment requirements.