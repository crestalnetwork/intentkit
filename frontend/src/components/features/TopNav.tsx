"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import iconSvg from "@/app/icon.svg";

export function TopNav() {
  const pathname = usePathname();

  return (
    <div className="mr-4 hidden md:flex">
      <Link className="mr-6 flex items-center space-x-2" href="/">
        <Image src={iconSvg} alt="IntentKit" width={56} height={56} />
        <span className="hidden font-bold sm:inline-block">IntentKit</span>
      </Link>
      <nav className="flex items-center space-x-6 text-sm font-medium">
        <Link
          href="/lead"
          className={cn(
            "transition-colors hover:text-foreground/80",
            pathname.startsWith("/lead")
              ? "text-foreground font-bold"
              : "text-foreground/60"
          )}
        >
          Lead
        </Link>
        <Link
          href="/agents"
          className={cn(
            "transition-colors hover:text-foreground/80",
            pathname.startsWith("/agents") || pathname.startsWith("/agent/")
              ? "text-foreground font-bold"
              : "text-foreground/60"
          )}
        >
          Agents
        </Link>
        <Link
          href="/tasks"
          className={cn(
            "transition-colors hover:text-foreground/80",
            pathname.startsWith("/tasks")
              ? "text-foreground font-bold"
              : "text-foreground/60"
          )}
        >
          Tasks
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
      </nav>
    </div>
  );
}
