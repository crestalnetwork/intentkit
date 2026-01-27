"use client";

import { useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bot, Pencil, MoreVertical, Archive, Plus, MoreHorizontal, Trash, Power } from "lucide-react";
import Link from "next/link";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import cronstrue from "cronstrue";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { agentApi, chatApi, autonomousApi, AutonomousTask } from "@/lib/api";

export default function AgentTasksPage() {
  const params = useParams();
  const agentId = params.id as string;

  // Fetch agent data
  const { data: agent, isLoading: isLoadingAgent } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId),
    enabled: !!agentId,
  });

  // Fetch autonomous tasks
  const { 
    data: tasks = [], 
    isLoading: isLoadingTasks,
    refetch: refetchTasks 
  } = useQuery({
    queryKey: ["tasks", agentId],
    queryFn: () => autonomousApi.listTasks(agentId),
    enabled: !!agentId,
  });

  const [actionTask, setActionTask] = useState<{
    task: AutonomousTask;
    type: "toggle" | "delete";
  } | null>(null);

  const handleConfirmAction = async () => {
    if (!actionTask) return;
    try {
      if (actionTask.type === "toggle") {
        await autonomousApi.updateTask(agentId, actionTask.task.id, {
          enabled: !actionTask.task.enabled,
        });
      } else if (actionTask.type === "delete") {
        await autonomousApi.deleteTask(agentId, actionTask.task.id);
      }
      refetchTasks();
    } catch (error) {
      console.error("Failed to perform action:", error);
    } finally {
      setActionTask(null);
    }
  };

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

  // Thread actions
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
        activeTab="tasks"
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
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Autonomous Tasks</h2>
            <p className="text-muted-foreground">
              Manage autonomous scheduled tasks for this agent.
            </p>
          </div>
          <Button size="sm">
            <Plus className="mr-2 h-4 w-4" />
            New
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {isLoadingTasks ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-32 bg-muted animate-pulse rounded-md" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <div className="text-center text-muted-foreground p-8">
              No autonomous tasks configured for this agent.
            </div>
          ) : (
            <div className="space-y-4">
              {tasks.map((task: AutonomousTask) => (
                <Card key={task.id} className="w-full">
                  <CardHeader className="pb-2">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <CardTitle className="text-lg">
                          {task.name || "Untitled Task"}
                        </CardTitle>
                        <CardDescription>
                          {task.description || "No description provided"}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        {task.has_memory && (
                          <Badge variant="secondary" className="bg-blue-100 text-blue-800 hover:bg-blue-100">
                            Memory
                          </Badge>
                        )}
                        <Badge
                          variant={task.enabled ? "default" : "secondary"}
                        >
                          {task.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                        
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <span className="sr-only">Open menu</span>
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setActionTask({ task, type: "toggle" })}>
                              <Power className="mr-2 h-4 w-4" />
                              {task.enabled ? "Disable" : "Enable"}
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              className="text-destructive focus:text-destructive"
                              onClick={() => setActionTask({ task, type: "delete" })}
                            >
                              <Trash className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm mt-2">
                      <div>
                        <span className="font-semibold text-muted-foreground">
                          Schedule:{" "}
                        </span>
                        {task.cron ? (
                          <div className="flex flex-col">
                            <span>{(() => {
                              try {
                                return cronstrue.toString(task.cron);
                              } catch (e) {
                                return task.cron;
                              }
                            })()}</span>
                            <span className="text-xs text-muted-foreground font-mono mt-0.5">
                              {task.cron}
                            </span>
                          </div>
                        ) : (
                          `Every ${task.minutes} minutes`
                        )}
                      </div>
                      <div>
                        <span className="font-semibold text-muted-foreground">
                          Next Run:{" "}
                        </span>
                         {task.next_run_time ? new Date(task.next_run_time).toLocaleString() : "Not scheduled"}
                      </div>
                    </div>
                    {task.prompt && (
                      <div className="mt-4">
                         <div className="text-xs font-semibold text-muted-foreground mb-1">Prompt:</div>
                         <div className="p-3 bg-muted/50 rounded-md font-mono text-xs whitespace-pre-wrap max-h-40 overflow-y-auto">
                            {task.prompt}
                         </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      <AlertDialog open={!!actionTask} onOpenChange={(open) => !open && setActionTask(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              {actionTask && (
                actionTask.type === "toggle"
                  ? `This will ${
                      actionTask.task.enabled ? "disable" : "enable"
                    } the task "${actionTask.task.name ?? "Untitled"}".`
                  : `This will permanently delete the task "${actionTask.task.name ?? "Untitled"}". This action cannot be undone.`
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmAction}>
              {actionTask?.type === "delete" ? "Delete" : "Confirm"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
