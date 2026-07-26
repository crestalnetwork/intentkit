# Frontend Guide

## Tech Stack

- **Next.js 16+** (App Router, SSR mode — NOT static export)
- **Shadcn/ui** (components in `src/components/ui/`) + **Tailwind CSS**
- **TanStack Query v5** for server state
- Agent config forms are hardcoded field-by-field (`src/app/agent/new/AgentForm.tsx`),
  not generated from a backend schema. Field labels, help text and validation
  live there; only the LLM list (`/metadata/llms`) and toolset catalog
  (`/metadata/tools`) are fetched. Keep the constraints in step with
  `AgentUpdate` in `intentkit/models/agent/user_input.py`.
- **Lucide React** for icons
- Native `fetch` as HTTP client
- API communication: REST + SSE streaming for chat

## Directory Structure

```
src/
├── app/                # Pages (App Router)
│   ├── agents/         # Agent list
│   ├── agent/[id]/     # Agent detail, chat, tasks
│   ├── posts/          # Post list
│   ├── post/           # Post detail
│   ├── timeline/       # Activity timeline
│   ├── layout.tsx      # Root layout + providers
│   └── providers.tsx   # TanStack Query provider
├── components/
│   ├── ui/             # Shadcn primitives (Button, Input, etc.)
│   └── features/       # Business components (ChatSidebar, AgentCard, etc.)
├── lib/
│   ├── api.ts          # All API client functions (agentApi, chatApi, activityApi, postApi, autonomousApi)
│   ├── config.ts       # Environment config (NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_AWS_S3_CDN_URL)
│   └── utils.ts        # Helpers (cn, etc.)
├── hooks/              # Custom hooks
└── types/              # TypeScript types (agent, chat, memory)
```

## API & Dev Setup

- Dev server: `npm run dev` on `:3000`, proxies `/api/*` → `http://127.0.0.1:8000` (configured in `next.config.ts` rewrites)
- Override proxy: set `NEXT_PUBLIC_API_BASE_URL` in `.env.local`
- All API functions are centralized in `src/lib/api.ts` — add new endpoints there
- SSE streaming: chat uses `POST /agents/{aid}/chats/{chat_id}/messages` with `stream: true`, parsed as SSE events

## Rules

- **Shadcn first**: use existing components from `src/components/ui/`. If missing, install via `npx shadcn@latest add <component>`
- **Tailwind only**: no custom CSS files or CSS modules
- **Lint after changes**: run `npm run lint` and fix all errors before committing
- **Typecheck after changes**: run `npm run typecheck` and fix all errors
