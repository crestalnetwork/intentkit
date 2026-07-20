"use client";

import { useEffect } from "react";

/**
 * Rewrites the current URL to use the agent's slug instead of its ID.
 * Only triggers when slug is available and differs from the current path segment.
 */
export function useAgentSlugRewrite(
  agentId: string,
  slug: string | null | undefined,
) {
  useEffect(() => {
    if (!slug || !agentId || agentId === slug) return;
    const currentPath = window.location.pathname;
    if (!currentPath.includes(`/agent/${agentId}`)) return;
    const newPath = currentPath.replace(`/agent/${agentId}`, `/agent/${slug}`);
    const nextUrl = `${newPath}${window.location.search}${window.location.hash}`;
    window.history.replaceState(window.history.state, "", nextUrl);
  }, [slug, agentId]);
}
