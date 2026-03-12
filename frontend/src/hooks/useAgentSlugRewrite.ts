"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Rewrites the current URL to use the agent's slug instead of its ID.
 * Only triggers when slug is available and differs from the current path segment.
 */
export function useAgentSlugRewrite(
  agentId: string,
  slug: string | null | undefined,
) {
  const router = useRouter();
  useEffect(() => {
    if (!slug || !agentId || agentId === slug) return;
    const currentPath = window.location.pathname;
    if (!currentPath.includes(`/agent/${agentId}`)) return;
    const newPath = currentPath.replace(`/agent/${agentId}`, `/agent/${slug}`);
    const search = window.location.search;
    router.replace(`${newPath}${search}`);
  }, [slug, agentId, router]);
}
