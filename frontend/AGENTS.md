# Frontend Architecture Guide for IntentKit

This guide outlines the architecture for the IntentKit frontend, designed for self-hosted, single-user agent management.

## 1. Technology Stack

We use a modern, "T3-ish" stack optimized for developer experience and AI-assisted coding.

-   **Framework**: **Next.js 15+ (App Router)**
    -   **Mode**: Static Export (`output: 'export'`). The frontend is compiled to pure HTML/CSS/JS and served by the FastAPI backend. No Node.js server is required in production.
    -   **Language**: TypeScript.

-   **UI System**: **Shadcn/ui** + **Tailwind CSS**
    -   **Shadcn/ui**: Headless components (Radix UI) with Tailwind styling. Components are copied into `src/components/ui`, allowing full customization.
    -   **Tailwind CSS**: Utility-first CSS framework for rapid styling.
    -   **Icons**: Lucide React.

-   **State Management**:
    -   **TanStack Query (React Query) v5**: Manages server state (fetching agents, chat history, status polling). Handles caching, loading states, and revalidation.
    -   **Zustand**: Manages global client-side UI state (e.g., sidebar toggle, active theme) if necessary.

-   **Communication**:
    -   **REST API**: Standard CRUD operations via `fetch` or `ky`.
    -   **Server-Sent Events (SSE)**: For real-time streaming of LLM responses from the agent.

## 2. Directory Structure

```text
frontend/
├── public/             # Static assets
├── src/
│   ├── app/            # Next.js App Router pages
│   │   ├── layout.tsx  # Root layout (providers, sidebar)
│   │   ├── page.tsx    # Dashboard / Agent List
│   │   └── agents/
│   │       └── [id]/   # Agent Detail & Chat Interface
│   ├── components/
│   │   ├── ui/         # Shadcn primitive components (Button, Input, etc.)
│   │   └── features/   # Business logic components (ChatWindow, AgentCard)
│   ├── lib/            # Utilities
│   │   ├── api.ts      # API client configuration
│   │   └── utils.ts    # Helper functions (cn, etc.)
│   ├── hooks/          # Custom React hooks
│   └── types/          # TypeScript definitions
├── next.config.ts      # Next.js configuration
├── tailwind.config.ts  # Tailwind configuration
└── package.json
```

## 3. Key Design Patterns

### Data Fetching
-   Use **TanStack Query** hooks (`useQuery`, `useMutation`) for all API interactions.
-   Do not use `useEffect` for data fetching.
-   Define query keys in a centralized factory or consistent pattern (e.g., `['agents', id]`) to enable easy invalidation.

### Streaming (Chat)
-   Use the native `fetch` API or a lightweight wrapper to handle SSE streams from FastAPI.
-   Maintain a local message list state that appends chunks as they arrive.

### Component Composition
-   Prefer **Composition** over Inheritance.
-   Keep components small and focused.
-   Use Shadcn components as building blocks.

## 4. Development Workflow

1.  **Prerequisites**: Node.js 24+.
2.  **Setup**: `npm install`.
3.  **Run**: `npm run dev`.
    -   The frontend runs on `localhost:3000`.
    -   API requests to `/api/*` are proxied to the FastAPI backend running on `localhost:8000` (configured in `next.config.ts`).

## 5. Deployment (Self-Hosted)

1.  **Build**: `npm run build`.
    -   This generates a static `out/` directory.
2.  **Serve**:
    -   The FastAPI backend mounts the `out/` directory as static files.
    -   The backend serves `index.html` for the root path and handles SPA routing fallback (if necessary, though static export usually relies on hash routing or specific file serving).

## 6. Rules for AI Agents

-   **Shadcn First**: When asked to create UI, always prefer using existing Shadcn components from `src/components/ui`. If a component is missing, instruct the user to install it via `npx shadcn@latest add <component>`.
-   **Tailwind Only**: Do not write custom CSS files or modules. Use Tailwind classes.
-   **Type Safety**: Ensure all props and API responses are strictly typed.