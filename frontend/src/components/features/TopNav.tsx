"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export function TopNav() {
  const pathname = usePathname();

  const isAgentsActive = 
    pathname === "/" || 
    (pathname.startsWith("/agent") && !pathname.includes("/activities") && !pathname.includes("/posts"));
    // Note: If /agent/1/posts is visited, user might consider it "Agents" or "Posts". 
    // Given the structure, Agent details usually fall under Agents.
    // However, if I am at /agent/1/activities or /posts, I want those specific tabs active if they existed.
    // But currently we have specific top-level "Timeline" (/timeline) and "Posts" (/posts).
    // Let's strictly follow the top-level meaning.
    // Agents: / or /agent/...
    // Timeline: /timeline
    // Posts: /posts or /post/... (Global posts)

  return (
    <div className="mr-4 hidden md:flex">
      <Link className="mr-6 flex items-center space-x-2" href="/">
        <span className="hidden font-bold sm:inline-block">IntentKit</span>
      </Link>
      <nav className="flex items-center space-x-6 text-sm font-medium">
        <Link
          href="/"
          className={cn(
            "transition-colors hover:text-foreground/80",
            pathname === "/" || (pathname.startsWith("/agent") && !pathname.startsWith("/timeline") && !pathname.startsWith("/posts"))
              ? "text-foreground font-bold"
              : "text-foreground/60"
          )}
        >
          Agents
        </Link>
        <Link
          href="/timeline"
          className={cn(
            "transition-colors hover:text-foreground/80",
            pathname.startsWith("/timeline")
              ? "text-foreground font-bold"
              : "text-foreground/60"
          )}
        >
          Timeline
        </Link>
        <Link
          href="/posts"
          className={cn(
            "transition-colors hover:text-foreground/80",
            pathname.startsWith("/posts") || pathname.startsWith("/post/")
              ? "text-foreground font-bold"
              : "text-foreground/60"
          )}
        >
          Posts
        </Link>
      </nav>
    </div>
  );
}
