"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/api";
import Link from "next/link";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Bot } from "lucide-react";

export default function DiscoverAgentsPage() {
  const { data: agents, isLoading } = useQuery({
    queryKey: ["public-agents"],
    queryFn: publicApi.getAgents,
  });

  if (isLoading) {
    return (
      <div className="text-center py-8 text-muted-foreground">Loading...</div>
    );
  }

  if (!agents || agents.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No public agents available yet.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((agent) => (
        <Link
          key={agent.id}
          href={`/agent/${agent.slug || agent.id}`}
          className="block rounded-lg border p-4 hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-start gap-3">
            <Avatar className="h-10 w-10">
              {agent.picture ? (
                <AvatarImage src={agent.picture} alt={agent.name || ""} />
              ) : null}
              <AvatarFallback className="bg-primary/10">
                <Bot className="h-5 w-5 text-primary" />
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold truncate">
                  {agent.name || agent.id}
                </h3>
                <Badge
                  variant="secondary"
                  className="text-xs shrink-0"
                >
                  Public
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                {agent.description || agent.purpose || "No description"}
              </p>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
