# P0: Team-Based Billing Migration

## Context

Current billing system charges individual users (`OwnerType.USER`). We need to switch to team-based billing where the **team that owns the agent always pays**. This is the foundation for all future billing features.

Key decisions:
- Deprecate `OwnerType.USER` for billing — all charges go to `OwnerType.TEAM`
- `user_id` in CreditEvent still records who triggered the action (audit trail)
- `team_id` in CreditEvent records who was billed
- Free credits / daily quota zeroed out (will be tied to pricing plans later)
- A simple script to add reward credits to teams

---

## Step 1: Zero out free quota defaults

**File:** `intentkit/models/app_setting.py`
- Line 104: `free_quota` default `480` → `0`
- Line 111: `refill_amount` default `20` → `0`

---

## Step 2: Change expense function signatures

**File:** `intentkit/core/credit/expense.py`

For all three functions (`expense_message` L86, `expense_skill` L467, `expense_summarize` L793):
1. Rename parameter `user_id: str` → `team_id: str`
2. Add parameter `user_id: str | None = None` (for audit trail)
3. Change `OwnerType.USER` → `OwnerType.TEAM` in `expense_in_session` / `get_or_create_in_session` calls
4. Change `owner_id=user_id` → `owner_id=team_id`
5. In `CreditEventTable(...)` creation: keep `user_id=user_id`, add `team_id=team_id`
6. In fee check `user_id != agent.owner` → `team_id != agent.team_id` (this will always be equal, so fee_agent_amount = 0, which is correct)
7. Budget tracking: `f"base_llm:{user_id}"` → `f"base_llm:{team_id}"`

Also update:
- `skill_cost()` (L408): rename `user_id` → `team_id`, same fee check change
- `expense_skill_internal_llm()` (L1124): rename `user_id` → `team_id`, add `user_id` param, pass both to `expense_skill`

---

## Step 3: Change payer determination in engine

**File:** `intentkit/core/engine.py`

### Payer logic (L617-626)
```python
# Before:
payer = user_message.user_id
if user_message.author_type in [TELEGRAM, DISCORD, ...]:
    payer = agent.owner

# After:
# Normal user conversations: user's team pays
# Platform channels (Telegram/Discord/Twitter/API/X402): agent's team pays
payer = message.team_id  # user's team (from request)
if user_message.author_type in [TELEGRAM, DISCORD, TWITTER, API, X402]:
    payer = agent.team_id  # agent's team
```

If `payer` is None and `payment_enabled` is True, raise error — agent/user must belong to a team.

Note: `message.team_id` comes from `ChatMessageRequest.team_id` (L153-156 in chat.py), already available in engine via the original `message` object (L649).

### `_validate_payment` (L250-303)
- L277: `OwnerType.USER` → `OwnerType.TEAM`
- L261: Validate `payer` (team_id) is set, raise `IntentKitAPIError(500, "PaymentError", "Payment is enabled but no team_id available")`
- L288: Abuse check — remove (free_credits will be 0, and payer is always a team)

### Expense call sites — pass both `team_id` and `user_id`:
- L390-397: `expense_message(session, team_id=payer, user_id=user_message.user_id, ...)`
- L503-510: same
- L518-527: `expense_skill(session, team_id=payer, user_id=user_message.user_id, ...)`

**File:** `intentkit/core/system_skills/read_webpage.py`
- L168: `expense_skill_internal_llm(...)` — pass `team_id` and `user_id` separately

---

## Step 4: Update income functions

**File:** `intentkit/core/credit/reward.py`
- Rename `user_id` → `team_id` in function signature
- L62: `OwnerType.USER` → `OwnerType.TEAM`, `owner_id=team_id`
- L82: `user_id=None, team_id=team_id` in CreditEventTable
- Update alert message

**File:** `intentkit/core/credit/recharge.py`
- Same pattern as reward

**File:** `intentkit/core/credit/adjustment.py`
- Same pattern: `user_id` → `team_id`, `OwnerType.USER` → `OwnerType.TEAM`

**File:** `intentkit/core/credit/list_events.py`
- Rename `list_credit_events_by_user` → `list_credit_events_by_team`
- L48: `OwnerType.USER` → `OwnerType.TEAM`, param `user_id` → `team_id`

---

## Step 5: Update credit account creation logic

**File:** `intentkit/models/credit/account.py`
- L662-665: The guard `if owner_type != OwnerType.USER` that zeros out free_quota — since defaults are now 0, this guard is no longer needed. Remove or simplify.

---

## Step 6: Create team reward script

**New file:** `scripts/reward_team.py`

CLI script: `python -m scripts.reward_team <team_id> <amount> [note]`
- Uses `reward()` from `intentkit.core.credit.reward`
- Auto-generates `upstream_tx_id`
- Prints new balance after reward

---

## Step 7: Update exports

**File:** `intentkit/core/credit/__init__.py`
- Rename `list_credit_events_by_user` → `list_credit_events_by_team` in exports

---

## Step 8: Update tests

- `tests/core/credit/test_expense.py` — update all calls with `team_id` param
- `tests/core/test_credit_soft_off.py` — update expense calls
- `tests/core/credit/test_list_events.py` (if exists) — update to team-based
- Add test for `scripts/reward_team.py`

---

## Verification

1. `ruff format && ruff check --fix` — no lint errors
2. `basedpyright` — no type errors in changed files
3. `pytest tests/core/credit/` — all credit tests pass
4. `pytest tests/core/test_credit_soft_off.py` — soft-off mode works
5. Manual: create a team credit account via reward script, verify balance
