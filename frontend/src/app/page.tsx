"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bot, MessageSquare, RefreshCw } from "lucide-react";
import { agentApi } from "@/lib/api";
import type { AgentResponse } from "@/types/agent";

export default function HomePage() {
  const {
    data: agents,
    isLoading,
    error,
    refetch,
    isRefetching,
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
            Manage and chat with your autonomous agents.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${isRefetching ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="h-[140px] bg-muted/50" />
            </Card>
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Error loading agents</p>
          <p className="text-sm mt-1">
            {error instanceof Error ? error.message : "Please try again later."}
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
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents?.map((agent: AgentResponse) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}
    </div>
  );
}

function AgentCard({ agent }: { agent: AgentResponse }) {
  const displayName = agent.name || agent.id;
  const displayDescription = agent.purpose || "No description available";

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {agent.picture ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={agent.picture}
                alt={displayName}
                className="h-10 w-10 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-5 w-5 text-primary" />
              </div>
            )}
            <CardTitle className="text-xl">{displayName}</CardTitle>
          </div>
        </div>
        <CardDescription className="line-clamp-2 min-h-[2.5rem] mt-2">
          {displayDescription}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="space-y-2 text-sm text-muted-foreground">
          <div className="flex items-center justify-between">
            <span>Model:</span>
            <span className="font-mono text-xs">{agent.model}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>ID:</span>
            <span className="font-mono text-xs">{agent.id}</span>
          </div>
          {agent.slug && (
            <div className="flex items-center justify-between">
              <span>Slug:</span>
              <span className="font-mono text-xs">{agent.slug}</span>
            </div>
          )}
        </div>
      </CardContent>
      <CardFooter>
        <Button asChild className="w-full" variant="default">
          <Link href={`/agent?id=${agent.id}`}>
            <MessageSquare className="mr-2 h-4 w-4" />
            Open Chat
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
