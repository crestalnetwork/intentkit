"use client";

import { useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  History,
  Pencil,
  MoreHorizontal,
  Trash,
  Power,
  Plus,
} from "lucide-react";
import Link from "next/link";
import cronstrue from "cronstrue";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { getImageUrl } from "@/lib/utils";
import { useAgentSlugRewrite } from "@/hooks/useAgentSlugRewrite";
import { buildChatThreadPath } from "@/lib/autonomousChat";
import { TaskDialog } from "@/app/tasks/TaskDialog";

export default function AgentTasksPage() {
  const params = useParams();
  const agentId = params.id as string;

  const { data: agent, isLoading: isLoadingAgent } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId),
    enabled: !!agentId,
  });

  useAgentSlugRewrite(agentId, agent?.slug);

  // Real agent ID for filtering/creating (agentId from params may be a slug)
  const resolvedId = agent?.id;

  // Threads for the sidebar.
  const {
    data: threads = [],
    isLoading: isLoadingThreads,
    refetch: refetchThreads,
  } = useQuery({
    queryKey: ["chats", resolvedId],
    queryFn: () => chatApi.listChats(resolvedId!),
    enabled: !!resolvedId,
  });

  // All team tasks; filtered below to the ones targeting this agent.
  const {
    data: allTasks = [],
    isLoading: isLoadingTasks,
    refetch: refetchTasks,
  } = useQuery({
    queryKey: ["all-tasks"],
    queryFn: () => autonomousApi.listTasks(),
  });

  const tasks = allTasks.filter(
    (t) => !!resolvedId && t.target_agent_id === resolvedId,
  );

  const [actionTask, setActionTask] = useState<{
    task: AutonomousTask;
    type: "toggle" | "delete";
  } | null>(null);
  const [isTaskDialogOpen, setIsTaskDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<AutonomousTask | null>(null);

  const handleSelectThread = useCallback(
    (threadId: string) => {
      window.location.href = buildChatThreadPath(agentId, threadId);
    },
    [agentId],
  );
  const handleNewThread = useCallback(() => {
    window.location.href = buildChatThreadPath(agentId, null);
  }, [agentId]);
  const handleUpdateTitle = useCallback(
    async (threadId: string, title: string) => {
      if (!resolvedId) return;
      await chatApi.updateChatSummary(resolvedId, threadId, title);
      await refetchThreads();
    },
    [resolvedId, refetchThreads],
  );
  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      if (!resolvedId) return;
      await chatApi.deleteChat(resolvedId, threadId);
      await refetchThreads();
    },
    [resolvedId, refetchThreads],
  );

  const handleNewTask = () => {
    setEditingTask(null);
    setIsTaskDialogOpen(true);
  };
  const handleEditTask = (task: AutonomousTask) => {
    setEditingTask(task);
    setIsTaskDialogOpen(true);
  };
  const handleSaveTask = async (taskData: Partial<AutonomousTask>) => {
    if (editingTask) {
      await autonomousApi.updateTask(editingTask.id, taskData);
    } else {
      await autonomousApi.createTask(
        taskData as Omit<AutonomousTask, "id" | "chat_id">,
      );
    }
    refetchTasks();
  };
  const handleConfirmAction = async () => {
    if (!actionTask) return;
    try {
      if (actionTask.type === "toggle") {
        await autonomousApi.updateTask(actionTask.task.id, {
          enabled: !actionTask.task.enabled,
        });
      } else if (actionTask.type === "delete") {
        await autonomousApi.deleteTask(actionTask.task.id);
      }
      refetchTasks();
    } finally {
      setActionTask(null);
    }
  };

  const displayName = agent?.name || agent?.id || agentId;
  const canEdit = !agent?.owner || agent.owner === "system";

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
        enableActivity={
          agent?.enable_activity !== false || agent?.enable_post !== false
        }
        enablePost={agent?.enable_post !== false}
      />

      <div className="flex-1 flex flex-col p-6 overflow-hidden">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <Link href={`/agent/${agentId}`} className="flex items-center gap-3">
            {agent?.picture ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={getImageUrl(agent.picture) ?? ""}
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
                {agent?.description || "No description"}
              </p>
            </div>
          </Link>
          {canEdit && (
            <Button onClick={handleNewTask}>
              <Plus className="mr-2 h-4 w-4" />
              New Task
            </Button>
          )}
        </div>

        <div className="mb-4">
          <h2 className="text-lg font-bold tracking-tight">Agent Tasks</h2>
          <p className="text-xs text-muted-foreground">
            Autonomous tasks assigned to run on this agent.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoadingTasks ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div
                  key={i}
                  className="h-32 bg-muted animate-pulse rounded-md"
                />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <div className="rounded-lg border border-border p-8 text-center">
              <Bot className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">No tasks found</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                This agent has no autonomous tasks assigned to it.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {tasks.map((task) => (
                <Card key={task.id} className="w-full">
                  <CardHeader className="pb-2">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <CardTitle className="text-lg">
                          <Link
                            href={`/tasks/${task.id}`}
                            className="hover:underline"
                          >
                            {task.name || "Untitled Task"}
                          </Link>
                        </CardTitle>
                        <CardDescription>
                          {task.description || "No description provided"}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={task.enabled ? "default" : "secondary"}>
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
                            <DropdownMenuItem asChild>
                              <Link href={`/tasks/${task.id}`}>
                                <History className="mr-2 h-4 w-4" />
                                View Runs
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() =>
                                setActionTask({ task, type: "toggle" })
                              }
                            >
                              <Power className="mr-2 h-4 w-4" />
                              {task.enabled ? "Disable" : "Enable"}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleEditTask(task)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() =>
                                setActionTask({ task, type: "delete" })
                              }
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
                            <span>
                              {(() => {
                                try {
                                  return cronstrue.toString(task.cron);
                                } catch {
                                  return task.cron;
                                }
                              })()}
                            </span>
                            <span className="text-xs text-muted-foreground font-mono mt-0.5">
                              {task.cron}
                            </span>
                          </div>
                        ) : (
                          "Not scheduled"
                        )}
                      </div>
                      <div>
                        <span className="font-semibold text-muted-foreground">
                          Next Run:{" "}
                        </span>
                        {task.next_run_time
                          ? new Date(task.next_run_time).toLocaleString()
                          : "Not scheduled"}
                      </div>
                    </div>
                    {task.prompt && (
                      <div className="mt-4">
                        <div className="text-xs font-semibold text-muted-foreground mb-1">
                          Prompt:
                        </div>
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

      <AlertDialog
        open={!!actionTask}
        onOpenChange={(open) => !open && setActionTask(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              {actionTask &&
                (actionTask.type === "toggle"
                  ? `This will ${actionTask.task.enabled ? "disable" : "enable"} the task "${actionTask.task.name ?? "Untitled"}".`
                  : `This will permanently delete the task "${actionTask.task.name ?? "Untitled"}". This action cannot be undone.`)}
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

      <TaskDialog
        open={isTaskDialogOpen}
        onOpenChange={setIsTaskDialogOpen}
        task={editingTask}
        onSave={handleSaveTask}
        defaultTargetAgentId={resolvedId}
      />
    </div>
  );
}
