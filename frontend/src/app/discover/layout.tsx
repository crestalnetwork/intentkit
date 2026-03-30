"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export default function DiscoverLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const tabs = [
    {
      href: "/discover",
      label: "Agents",
      match: (p: string) =>
        p === "/discover" || p.startsWith("/discover/agents"),
    },
    {
      href: "/discover/timeline",
      label: "Timeline",
      match: (p: string) => p.startsWith("/discover/timeline"),
    },
    {
      href: "/discover/posts",
      label: "Posts",
      match: (p: string) => p.startsWith("/discover/posts"),
    },
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
                : "border-transparent text-muted-foreground hover:text-foreground",
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
