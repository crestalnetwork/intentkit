# P0: Team-Based Billing Migration — COMPLETED

All steps in this plan have been implemented:

- Step 1: Free quota defaults zeroed out (now driven by TeamPlan configs)
- Step 2: Expense functions use `team_id` parameter with `OwnerType.TEAM`
- Step 3: Engine payer logic uses team-based billing
- Step 4: Income functions (reward, recharge, adjustment) updated to team-based
- Step 5: Credit account creation logic updated
- Step 6: `scripts/reward_team.py` created
- Step 7: Exports updated (`list_credit_events_by_team`)
- Step 8: Tests updated
