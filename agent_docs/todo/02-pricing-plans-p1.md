# P1: Pricing Plans & Stripe Integration — PARTIALLY COMPLETED

## Completed

- Plan model: `TeamPlan` enum (NONE/FREE/PRO/MAX) with `PLAN_CONFIGS` defining free_quota, refill_amount, monthly_permanent_credits
- Team plan assignment: teams get plan on creation based on signup method
- Plan-based quota allocation: credit account creation reads from team's plan config
- Monthly plan credit issuance: `issue_all_plan_credits()` runs hourly for PRO/MAX teams
- Plan expiration tracking: `plan_expires_at` and `next_credit_issue_at` fields on TeamTable

## Remaining (TBD)

- Stripe integration for payment processing
- Stripe checkout session creation
- Stripe webhook handling (payment success, subscription changes)
- Subscription lifecycle management (create, upgrade, downgrade, cancel)
- Admin API for plan management
