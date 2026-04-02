# P1: Pricing Plans & Stripe Integration

## Context

After P0 (team billing migration), we need:
1. Pricing plan/tier model (Free / Pro / Enterprise)
2. Each plan defines: free_quota, refill_amount, rate limits, feature gates
3. Stripe integration for payment processing
4. Team ↔ Plan binding
5. Subscription lifecycle management (create, upgrade, downgrade, cancel)

## Scope (TBD)

- Plan model & DB schema
- Stripe checkout session creation
- Stripe webhook handling (payment success, subscription changes)
- Team plan assignment and enforcement
- Plan-based quota allocation (replaces global PaymentSettings defaults)
- Admin API for plan management

## Dependencies

- Requires P0 (team billing) to be complete
- Requires Stripe account setup and API keys

## Notes

- Details to be refined after P0 is implemented and validated
