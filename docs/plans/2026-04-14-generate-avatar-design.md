# Generate Avatar — Design

## Goal

Replace the "Remove" button on user-profile and team-profile avatar uploads in
`intentcat` with a "Generate" button. Clicking opens a dialog where the user
describes what they want; the backend generates an image, charges the team's
credit account, and updates the avatar.

Scope: `intentcat/` (team frontend) and `app/team/` backend only. The main
`frontend/` has no user/team avatar (only agent picture, which already has
auto-generation) and is not touched.

## UX Flow

1. User clicks **Generate** (replaces **Remove**).
2. Dialog opens with a textarea, placeholder
   `Describe your avatar, e.g. "a cheerful cartoon fox wearing glasses"`,
   and a **Generate** button.
3. On submit: spinner; call `POST /teams/{team_id}/generate-picture` with
   `{prompt}`.
4. On success: `onChange(path)` updates the avatar field, dialog closes, toast
   `Avatar generated (-10 credits)`.
5. On failure: show error inline in dialog, dialog stays open.

No preview / no confirm step — success saves directly. User can regenerate by
clicking **Generate** again.

## Billing

A **new event type MEDIA** (repurposed from the unused VOICE) is introduced as
a dedicated billing path for direct-API media generation (avatar now, possibly
other media later).

### Renames (no data migration needed — VOICE was never used)

| File | Before | After |
|---|---|---|
| `intentkit/models/credit/base.py` | `DEFAULT_PLATFORM_ACCOUNT_VOICE = "platform_voice"` | `DEFAULT_PLATFORM_ACCOUNT_MEDIA = "platform_media"` |
| `intentkit/models/credit/__init__.py` | export `DEFAULT_PLATFORM_ACCOUNT_VOICE` | export `DEFAULT_PLATFORM_ACCOUNT_MEDIA` |
| `intentkit/models/credit/event.py` | `VOICE = "voice"` | `MEDIA = "media"` |
| `intentkit/models/credit/transaction.py` | `RECEIVE_BASE_VOICE = "receive_base_voice"` | `RECEIVE_BASE_MEDIA = "receive_base_media"` |

Historical migration script `scripts/migrate_credit_transaction_amounts.py`
still references `'receive_base_voice'` — leave as-is (one-time migration on
past data).

### Pricing

- **Base price**: `5` credits per generation (anti-abuse, not cost-recovery)
- **Platform fee**: default 100% → total ~10 credits per call
- **No agent fee** (no agent involved)
- **When payment_enabled = false** (dev): `base_discount_amount = base_original_amount`, total 0 — free in dev mode, same as other expense paths

### New expense function

`intentkit/core/credit/expense.py::expense_media`

```python
async def expense_media(
    session: AsyncSession,
    team_id: str,
    user_id: str,
    upstream_tx_id: str,
    base_original_amount: Decimal,
) -> CreditEvent:
    """Deduct credits from a team account for direct-API media generation
    (e.g. avatar generation). No agent context, no chat context.
    """
```

Structure mirrors `expense_skill` but:
- `event_type = EventType.MEDIA`
- `upstream_type = UpstreamType.API`
- `agent_id = None`, `message_id = None`, `skill_call_id = None`, `skill_name = None`
- Destination platform account: `DEFAULT_PLATFORM_ACCOUNT_MEDIA`
- No agent fee calculation; only platform fee
- `base_llm_amount` and `base_skill_amount` stay `0` (not applicable)
- `base_amount`, `base_original_amount`, `base_discount_amount` set normally
- `base_free_amount` / `base_reward_amount` / `base_permanent_amount` populated
  from the `CreditAccount.expense_in_session` result details
- Single debit (team) + two credits (platform_media, platform_fee)

## Backend

### New: `intentkit/core/avatar.py::generate_avatar_from_description`

```python
_USER_AVATAR_SYSTEM_PROMPT = """\
You are an expert avatar designer. Based on the user-provided description below,
write a concise visual description for a profile picture (avatar).

Requirements for the avatar:
- Modern, clean, and visually striking design suitable as a profile picture
- A single central subject or icon
- Works well at small sizes (like a chat avatar)
- Abstract or stylized — do NOT include any text, letters, or words in the image
- Square composition with the subject centered

Output ONLY the image generation prompt, nothing else."""

async def generate_avatar_from_description(
    description: str, s3_prefix: str
) -> str | None:
    """Generate an avatar from a free-text user description.

    Args:
        description: Free-text user description of the desired avatar.
        s3_prefix: S3 key prefix for storing the result (e.g. "avatars/user/{uid}").

    Returns:
        Relative S3 path on success, None on failure.
    """
```

Reuses existing `generate_image_prompt_from_profile()`, `select_model_and_generate()`,
and `_normalize_avatar()`. Stores the final PNG at
`{s3_prefix}/{XID}.png`.

### New API endpoint

File: `app/team/team.py` (team router — it's a team-scoped operation that
charges the team, used by both user-avatar and team-picture UIs).

```
POST /teams/{team_id}/generate-avatar
Body: { "prompt": "<=500 chars" }
Auth: verify_team_member
Response: { "path": "avatars/..." }
```

Request model:
```python
class GenerateAvatarRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
```

Flow (inside a single DB session/transaction):
1. Validate prompt.
2. Call `generate_avatar_from_description(prompt, s3_prefix=f"avatars/generated/{team_id}")`.
3. If generation fails → raise 502 `AvatarGenerationFailed`.
4. Call `expense_media(session, team_id, user_id, upstream_tx_id=str(XID()), base_original_amount=Decimal("5"))`.
5. Commit. If expense fails (e.g. insufficient credits) → raise 402 `InsufficientCredits`; the S3 object stays as orphan (acceptable — no user-visible impact, cleanable later).
6. Return `{path}`.

Charge-after-success matches the user rule "成功了扣". Orphan S3 objects on
rare expense failures are not this task's concern.

## Frontend (intentcat)

### New component: `src/components/features/AvatarGenerateDialog.tsx`

```typescript
interface AvatarGenerateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  teamId: string;                       // required to charge a team
  onGenerated: (path: string) => void;  // called on success
}
```

- `Dialog` + `DialogHeader` (title "Generate Avatar")
- `Textarea` (required, maxLength 500)
- `Button` **Generate** (loading spinner while pending)
- `Button` **Cancel**
- On success: `onGenerated(path)`, close, toast "Avatar generated (-10 credits)"
- On error: inline error below textarea, dialog stays open

### `src/components/features/UserAvatarUpload.tsx`

- New prop: `teamId?: string` (optional — parent provides from `LAST_TEAM_KEY`)
- Replace **Remove** button (Trash2) with **Generate** button (Sparkles icon)
  - Always visible (not gated on `value`)
  - If `!teamId`: `disabled` + tooltip "Join a team first"
- Clicking opens `AvatarGenerateDialog`

### `src/components/features/PictureUpload.tsx`

- Already has `teamId` prop
- Replace **Remove** → **Generate** (same UX as above)

### `src/app/account/page.tsx`

Read `LAST_TEAM_KEY` on mount and pass to `UserAvatarUpload`:

```typescript
const [activeTeamId, setActiveTeamId] = useState<string | null>(null);
useEffect(() => {
  if (typeof window !== "undefined") {
    setActiveTeamId(localStorage.getItem(LAST_TEAM_KEY));
  }
}, []);
```

Also fall back to the first team from `userApi.getTeams()` if localStorage is
empty (first-time user who hasn't visited `/t/[teamId]/` yet).

### `src/lib/api.ts`

New method on `teamApi`:

```typescript
async generateAvatar(teamId: string, prompt: string): Promise<{ path: string }> {
  const res = await authFetch(
    `${API_BASE}/teams/${teamId}/generate-avatar`,
    { method: "POST", body: JSON.stringify({ prompt }) }
  );
  return res.json();
}
```

## Error Handling

| Error | HTTP | Frontend display |
|---|---|---|
| Invalid prompt (empty / too long) | 400 | inline in dialog |
| Team not found / not a member | 403 | toast |
| Avatar generation failed (all providers down) | 502 | inline in dialog, "Try again" |
| Insufficient credits | 402 | inline in dialog, "Not enough credits" |
| S3 storage not configured | 500 | inline in dialog, generic |

## Out of Scope

- Preview / retry within the dialog (user chose direct-save UX)
- Rate limiting beyond credit charge
- Orphan S3 object cleanup
- Main `frontend/` changes (no user/team avatar there)
- Agent picture generation (already exists as auto-gen)

## Testing

- Unit: `expense_media` correctly deducts, creates event with
  `EventType.MEDIA`, zero agent fee.
- Unit: enum rename (`MEDIA`, `DEFAULT_PLATFORM_ACCOUNT_MEDIA`,
  `RECEIVE_BASE_MEDIA`) still importable; existing imports updated.
- Integration: `POST /teams/{team_id}/generate-avatar` happy path + 402 +
  unauthorized team.
- Manual: run intentcat dev, click Generate on both user account and team
  settings pages, verify avatar updates and credit deducted.
