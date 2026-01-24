"use client";

import { useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bot, Pencil, MoreVertical, Archive } from "lucide-react";
import Link from "next/link";
import { Timeline } from "@/components/features/Timeline";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { agentApi, chatApi } from "@/lib/api";

export default function AgentActivitiesPage() {
  const params = useParams();
  const agentId = params.id as string;

  // Fetch agent data
  const { data: agent, isLoading: isLoadingAgent } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId),
    enabled: !!agentId,
  });

  // Fetch thread list for sidebar
  const {
    data: threads = [],
    isLoading: isLoadingThreads,
    refetch: refetchThreads,
  } = useQuery({
    queryKey: ["chats", agentId],
    queryFn: () => chatApi.listChats(agentId),
    enabled: !!agentId,
  });

  // Thread actions (minimal - just for sidebar to work)
  const handleSelectThread = useCallback(
    (threadId: string) => {
      window.location.href = `/agent/${agentId}?thread=${threadId}`;
    },
    [agentId]
  );

  const handleNewThread = useCallback(() => {
    window.location.href = `/agent/${agentId}`;
  }, [agentId]);

  const handleUpdateTitle = useCallback(
    async (threadId: string, title: string) => {
      await chatApi.updateChatSummary(agentId, threadId, title);
      await refetchThreads();
    },
    [agentId, refetchThreads]
  );

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      await chatApi.deleteChat(agentId, threadId);
      await refetchThreads();
    },
    [agentId, refetchThreads]
  );

  const displayName = agent?.name || agent?.id || agentId;

  if (isLoadingAgent) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)]">
        <div className="w-64 border-r bg-muted/30 animate-pulse" />
        <div className="flex-1 p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-8 w-1/3 bg-muted rounded" />
            <div className="h-[500px] bg-muted rounded" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar */}
      <ChatSidebar
        agentId={agentId}
        activeTab="activities"
        threads={threads}
        currentThreadId={null}
        isNewThread={false}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onUpdateTitle={handleUpdateTitle}
        onDeleteThread={handleDeleteThread}
        isLoading={isLoadingThreads}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col p-6 overflow-hidden">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" asChild>
              <Link href="/">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <div className="flex items-center gap-3">
              {agent?.picture ? (
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
              <div>
                <h1 className="text-xl font-bold">{displayName}</h1>
                <p className="text-sm text-muted-foreground line-clamp-1">
                  {agent?.purpose || "No description"}
                </p>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href={`/agents/${agentId}/edit`}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon" className="h-9 w-9">
                  <MoreVertical className="h-4 w-4" />
                  <span className="sr-only">More actions</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem className="text-destructive focus:text-destructive">
                  <Archive className="mr-2 h-4 w-4" />
                  Archive
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* Page Title */}
        <div className="mb-4">
          <h2 className="text-2xl font-bold tracking-tight">Agent Activities</h2>
          <p className="text-muted-foreground">
            Recent activities and events for this agent.
          </p>
        </div>

        {/* Content */}
        <div className="flex-1 rounded-xl border bg-card text-card-foreground shadow p-6 overflow-y-auto">
          <Timeline agentId={agentId} agentPicture={agent?.picture} />
        </div>
      </div>
    </div>
  );
}
