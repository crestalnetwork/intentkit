# Discover Page & Public Agent System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Discover page with Agents/Timeline/Posts sub-pages showing public agents (visibility >= 20), maintain a "public" virtual team feed, and make agent detail pages permission-aware.

**Architecture:** Public agents use owner/team "predefined". A virtual team "public" receives feed entries for all public agents. New `/public/*` API endpoints serve unauthenticated data. Frontend adds Discover page with tabs, and agent detail pages conditionally show Edit/Menu.

**Tech Stack:** Python/FastAPI (backend), Next.js 14 App Router + TanStack Query (frontend), SQLAlchemy 2.0, PostgreSQL

---

### Task 1: Change public agents owner/team to "predefined"

**Files:**
- Modify: `intentkit/core/public_agents.py` (lines 22-23)
- Modify: `app/api.py` (lifespan, around line 91)
- Modify: `app/team/api.py` (lifespan, around line 70)

**Step 1:** Update constants in `intentkit/core/public_agents.py`:
```python
OWNER = "predefined"
TEAM_ID = "predefined"
```

**Step 2:** In `app/api.py` lifespan, after `ensure_system_user_and_team()`, add creation of the "predefined" team and "public" virtual team. Same in `app/team/api.py`. Extract this into a shared function in `intentkit/core/public_agents.py`:

```python
async def ensure_public_agent_prerequisites() -> None:
    """Ensure 'predefined' user/team and 'public' virtual team exist."""
    from intentkit.models.team import TeamMemberTable, TeamRole, TeamTable
    from intentkit.models.user import UserTable

    async with get_session() as session:
        # Create "predefined" user if not exists
        if not await session.get(UserTable, "predefined"):
            session.add(UserTable(id="predefined"))

        # Create "predefined" team if not exists
        if not await session.get(TeamTable, "predefined"):
            session.add(TeamTable(id="predefined", name="predefined"))

        # Create predefined team membership if not exists
        if not await session.get(
            TeamMemberTable, {"team_id": "predefined", "user_id": "predefined"}
        ):
            session.add(
                TeamMemberTable(
                    team_id="predefined",
                    user_id="predefined",
                    role=TeamRole.OWNER,
                )
            )

        # Create "public" virtual team for public feed aggregation
        if not await session.get(TeamTable, "public"):
            session.add(TeamTable(id="public", name="public"))

        await session.commit()
```

**Step 3:** In `sync_public_agents()`, after creating/updating each agent, also auto-subscribe the "public" team:
```python
from intentkit.core.team.subscription import auto_subscribe_team
# After the main commit loop, subscribe public team to all synced agents
for agent_id, slug, agent_update, new_hash, description in agents_to_sync:
    try:
        await auto_subscribe_team("public", agent_id)
    except Exception:
        logger.exception("Failed to subscribe public team to %s", agent_id)
```

**Step 4:** In both lifespan functions, call `ensure_public_agent_prerequisites()` before `sync_public_agents()`.

---

### Task 2: Add public API endpoints (backend)

**Files:**
- Create: `app/local/public.py`
- Create: `app/team/public.py`
- Modify: `app/api.py` (register router)
- Modify: `app/team/api.py` (register router)
- Modify: `app/local/__init__.py` (export router)
- Modify: `app/team/__init__.py` (export router)

**Step 1:** Create `app/local/public.py` with these endpoints:

```python
from fastapi import APIRouter, Path, Query
from sqlalchemy import select

from intentkit.config.db import get_db, get_session
from intentkit.core.agent import get_agent
from intentkit.core.agent_post import get_agent_post
from intentkit.core.team.feed import query_activity_feed, query_post_feed
from intentkit.models.agent import AgentResponse, AgentTable
from intentkit.models.agent_activity import AgentActivity
from intentkit.models.agent_post import AgentPostBrief, AgentPost
from intentkit.models.team_feed import TeamFeedPage
from intentkit.utils.error import IntentKitAPIError

public_router = APIRouter(prefix="/public", tags=["Public"])

PUBLIC_TEAM_ID = "public"


@public_router.get("/agents", operation_id="public_list_agents")
async def list_public_agents() -> list[AgentResponse]:
    """List all public agents (visibility >= 20)."""
    async with get_session() as session:
        result = await session.execute(
            select(AgentTable)
            .where(AgentTable.visibility >= 20)
            .where(AgentTable.archived_at.is_(None))
            .order_by(AgentTable.created_at.desc())
        )
        agents = result.scalars().all()
        # Convert to AgentResponse (use from_agent for each)
        responses = []
        for agent_row in agents:
            from intentkit.models.agent import Agent
            agent = Agent.model_validate(agent_row)
            resp = await AgentResponse.from_agent(agent)
            responses.append(resp)
        return responses


@public_router.get("/timeline", operation_id="public_timeline")
async def public_timeline(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
) -> TeamFeedPage[AgentActivity]:
    """Get public activity timeline."""
    items, next_cursor = await query_activity_feed(PUBLIC_TEAM_ID, limit, cursor)
    return TeamFeedPage(items=items, next_cursor=next_cursor)


@public_router.get("/posts", operation_id="public_posts")
async def public_posts(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
) -> TeamFeedPage[AgentPostBrief]:
    """Get public posts feed."""
    items, next_cursor = await query_post_feed(PUBLIC_TEAM_ID, limit, cursor)
    return TeamFeedPage(items=items, next_cursor=next_cursor)


@public_router.get("/posts/{post_id}", operation_id="public_get_post")
async def public_get_post(post_id: str = Path(...)) -> AgentPost:
    """Get a single public post."""
    post = await get_agent_post(post_id)
    if not post:
        raise IntentKitAPIError(404, "NotFound", "Post not found")
    return post
```

**Step 2:** Create `app/team/public.py` with the same endpoints but using team-API style (no auth required for public endpoints).

**Step 3:** Register routers in `app/api.py`, `app/team/api.py`, and update `__init__.py` exports.

---

### Task 3: Fan out to "public" virtual team for public agents

**Files:**
- Modify: `intentkit/core/team/feed.py` (fan_out_activity and fan_out_post)

**Step 1:** Modify `fan_out_activity` to also fan out to "public" team if agent is public:

```python
async def fan_out_activity(
    activity_id: str, agent_id: str, created_at: datetime
) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(TeamSubscriptionTable.team_id).where(
                TeamSubscriptionTable.agent_id == agent_id
            )
        )
        team_ids = list(result.scalars().all())

        # Also check if agent is public (visibility >= 20) and add "public" team
        from intentkit.models.agent.db import AgentTable
        agent_row = await session.get(AgentTable, agent_id)
        if agent_row and agent_row.visibility is not None and agent_row.visibility >= 20:
            if "public" not in team_ids:
                team_ids.append("public")

        if not team_ids:
            return

        values = [
            {
                "team_id": tid,
                "activity_id": activity_id,
                "agent_id": agent_id,
                "created_at": created_at,
            }
            for tid in team_ids
        ]
        stmt = insert(TeamActivityFeedTable).values(values).on_conflict_do_nothing()
        await session.execute(stmt)
        await session.commit()
```

**Step 2:** Apply the same pattern to `fan_out_post`.

---

### Task 4: Add visibility and owner to frontend Agent type

**Files:**
- Modify: `frontend/src/types/agent.ts`
- Modify: `/Users/muninn/project/intentcat/src/types/agent.ts`

**Step 1:** Add fields to Agent interface in both projects:
```typescript
  owner: string | null;
  team_id: string | null;
  visibility: number | null;
```

---

### Task 5: Add public API functions to frontend

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `/Users/muninn/project/intentcat/src/lib/api.ts`

**Step 1:** Add `publicApi` object to both:
```typescript
export const publicApi = {
  async getAgents(): Promise<AgentResponse[]> {
    const response = await fetch(`${API_BASE}/public/agents`);
    if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
    return response.json();
  },

  async getTimeline(limit = 20, cursor?: string | null) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", cursor);
    const response = await fetch(`${API_BASE}/public/timeline?${params}`);
    if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
    return response.json();
  },

  async getPosts(limit = 20, cursor?: string | null) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", cursor);
    const response = await fetch(`${API_BASE}/public/posts?${params}`);
    if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
    return response.json();
  },

  async getPost(postId: string) {
    const response = await fetch(`${API_BASE}/public/posts/${postId}`);
    if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
    return response.json();
  },
};
```

For intentcat, use `authGet` for authenticated version or just `fetch` since these are public endpoints.

---

### Task 6: Add Discover page with tabs (frontend)

**Files:**
- Create: `frontend/src/app/discover/page.tsx`
- Create: `frontend/src/app/discover/agents/page.tsx`
- Create: `frontend/src/app/discover/timeline/page.tsx`
- Create: `frontend/src/app/discover/posts/page.tsx`
- Create: `frontend/src/app/discover/layout.tsx` (shared tab layout)

**Step 1:** Create shared layout with tabs:
```tsx
// frontend/src/app/discover/layout.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export default function DiscoverLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const tabs = [
    { href: "/discover", label: "Agents", match: (p: string) => p === "/discover" || p === "/discover/agents" },
    { href: "/discover/timeline", label: "Timeline", match: (p: string) => p === "/discover/timeline" },
    { href: "/discover/posts", label: "Posts", match: (p: string) => p === "/discover/posts" },
  ];

  return (
    <div className="container py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Discover</h1>
        <p className="text-muted-foreground mt-2">
          Explore public agents and their content.
        </p>
      </div>
      <div className="flex border-b mb-6">
        {tabs.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              tab.match(pathname)
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </Link>
        ))}
      </div>
      {children}
    </div>
  );
}
```

**Step 2:** Create `/discover/page.tsx` (redirects or shows agents):
```tsx
// This IS the agents tab (default)
"use client";
import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/api";
import { AgentCard } from "@/components/features/AgentCard";

export default function DiscoverAgentsPage() {
  const { data: agents, isLoading } = useQuery({
    queryKey: ["public-agents"],
    queryFn: publicApi.getAgents,
  });

  if (isLoading) return <div className="text-center py-8">Loading...</div>;

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {agents?.map((agent) => (
        <AgentCard key={agent.id} agent={agent} />
      ))}
    </div>
  );
}
```

**Step 3:** Create `/discover/agents/page.tsx` that re-exports the same component.

**Step 4:** Create `/discover/timeline/page.tsx` using `publicApi.getTimeline` with `useInfiniteQuery` and cursor pagination — same pattern as intentcat's `/feed` page.

**Step 5:** Create `/discover/posts/page.tsx` using `publicApi.getPosts` with `useInfiniteQuery` — same pattern as intentcat's `/posts` page.

**Step 6:** Mirror all above in intentcat at the same paths.

---

### Task 7: Add Discover to TopNav

**Files:**
- Modify: `frontend/src/components/features/TopNav.tsx`
- Modify: `/Users/muninn/project/intentcat/src/components/features/TopNav.tsx`

**Step 1:** Add Discover link after Posts in intentkit TopNav:
```tsx
<Link
  href="/discover"
  className={cn(
    "transition-colors hover:text-foreground/80",
    pathname.startsWith("/discover")
      ? "text-foreground font-bold"
      : "text-foreground/60"
  )}
>
  Discover
</Link>
```

**Step 2:** Same for intentcat TopNav (add after Posts link).

---

### Task 8: Make agent detail page permission-aware

**Files:**
- Modify: `frontend/src/app/agent/[id]/ClientPage.tsx` (lines 606-649)
- Modify: `/Users/muninn/project/intentcat/src/app/agent/[id]/ClientPage.tsx` (similar area)

**Step 1:** Add permission check logic. For local frontend:
```tsx
// Determine if user can edit this agent
const canEdit = agent?.owner === "system" || agent?.team_id === "system";
```

For intentcat (team frontend), also check team membership:
```tsx
const canEdit = agent?.team_id === teamId;
```

**Step 2:** Wrap Edit button and dropdown menu in permission check:
```tsx
{canEdit && (
  <div className="flex gap-2">
    <Button variant="outline" size="sm" asChild>
      <Link href={`/agent/${agentId}/edit`}>
        <Pencil className="mr-2 h-4 w-4" />
        Edit
      </Link>
    </Button>
    <DropdownMenu>
      {/* ... existing dropdown ... */}
    </DropdownMenu>
  </div>
)}
```

**Step 3:** Add "Public" badge after agent name if visibility >= 20:
```tsx
<h1 className="text-xl font-bold">
  {displayName}
  {agent?.visibility != null && agent.visibility >= 20 && (
    <Badge variant="secondary" className="ml-2 text-xs">Public</Badge>
  )}
</h1>
```

Import Badge from `@/components/ui/badge`.

**Step 4:** Apply same changes to activities, posts, and tasks sub-pages that also show Edit buttons.

---

### Task 9: Lint, type check, and test

**Files:** All modified files

**Step 1:** Run backend linting:
```bash
ruff format && ruff check --fix
basedpyright intentkit/core/public_agents.py intentkit/core/team/feed.py app/local/public.py app/team/public.py app/api.py app/team/api.py
```

**Step 2:** Run frontend type check:
```bash
cd frontend && npx tsc --noEmit
cd /Users/muninn/project/intentcat && npx tsc --noEmit
```

**Step 3:** Run tests:
```bash
pytest -m "not bdd" -x -q
```

---

### Task 10: Review with copilot and gemini

**Step 1:** Run simplify skill review.

**Step 2:** Run external reviews:
```bash
copilot --allow-all -s --stream off -p "Review the uncommitted code for the Discover page feature..."
gemini --approval-mode plan "Review the uncommitted code for the Discover page feature..."
```

**Step 3:** Address feedback and re-run lint/tests.
