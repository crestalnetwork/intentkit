
"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
} from "@/components/ui/card";
import { agentApi } from "@/lib/api";
import type { AgentResponse } from "@/types/agent";
import { AgentCard } from "@/components/features/AgentCard";

export default function HomePage() {
  const {
    data: agents,
    isLoading: isAgentsLoading,
    error: agentsError,
    refetch: refetchAgents,
    isRefetching: isAgentsRefetching,
  } = useQuery({
    queryKey: ["agents"],
    queryFn: agentApi.getAll,
  });

  return (
    <div className="container py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agents</h1>
          <p className="text-muted-foreground mt-2">
            Manage your autonomous agents.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchAgents()}
            disabled={isAgentsRefetching}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isAgentsRefetching ? "animate-spin" : ""
                }`}
            />
            Refresh Agents
          </Button>
        </div>
      </div>

      {isAgentsLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="h-[140px] bg-muted/50" />
            </Card>
          ))}
        </div>
      ) : agentsError ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Error loading agents</p>
          <p className="text-sm mt-1">
            {agentsError instanceof Error
              ? agentsError.message
              : "Please try again later."}
          </p>
        </div>
      ) : agents && agents.length === 0 ? (
        <div className="rounded-lg border border-border p-8 text-center">
          <Bot className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No agents found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Create an agent to get started.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[...(agents || [])]
            .sort(
              (a, b) =>
                new Date(b.updated_at).getTime() -
                new Date(a.updated_at).getTime()
            )
            .map((agent: AgentResponse) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
        </div>
      )}
    </div>
  );
}
