"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bot, Pencil, MoreHorizontal, Trash, Power } from "lucide-react";
import { getImageUrl } from "@/lib/utils";
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
import { autonomousApi, AutonomousTask } from "@/lib/api";
import { TaskDialog } from "@/app/agent/[id]/tasks/TaskDialog";
import { TaskBadgeActions } from "@/app/agent/[id]/tasks/TaskBadgeActions";
import { buildTaskLogsPath } from "@/lib/autonomousChat";

export default function AllTasksPage() {
  const {
    data: groups = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["all-tasks"],
    queryFn: () => autonomousApi.listAllTasks(),
  });

  const [actionTask, setActionTask] = useState<{
    task: AutonomousTask;
    agentId: string;
    type: "toggle" | "delete";
  } | null>(null);

  const [isTaskDialogOpen, setIsTaskDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<{
    task: AutonomousTask;
    agentId: string;
  } | null>(null);

  const handleEditTask = (agentId: string, task: AutonomousTask) => {
    setEditingTask({ task, agentId });
    setIsTaskDialogOpen(true);
  };

  const handleSaveTask = async (taskData: Partial<AutonomousTask>) => {
    if (!editingTask) return;
    try {
      await autonomousApi.updateTask(editingTask.agentId, editingTask.task.id, taskData);
      refetch();
    } catch (error) {
      console.error("Failed to save task:", error);
      throw error;
    }
  };

  const handleConfirmAction = async () => {
    if (!actionTask) return;
    try {
      if (actionTask.type === "toggle") {
        await autonomousApi.updateTask(
          actionTask.agentId,
          actionTask.task.id,
          { enabled: !actionTask.task.enabled },
        );
      } else if (actionTask.type === "delete") {
        await autonomousApi.deleteTask(actionTask.agentId, actionTask.task.id);
      }
      refetch();
    } catch (error) {
      console.error("Failed to perform action:", error);
    } finally {
      setActionTask(null);
    }
  };

  return (
    <div className="container py-10">
      <div className="max-w-[768px] mx-auto">
      <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">Tasks</h1>
          <p className="text-muted-foreground mt-2">
            All autonomous tasks across your agents.
          </p>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {[1, 2].map((i) => (
            <div key={i} className="space-y-3">
              <div className="h-10 w-48 bg-muted animate-pulse rounded" />
              <div className="h-32 bg-muted animate-pulse rounded-md" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Error loading tasks</p>
          <p className="text-sm mt-1">
            {error instanceof Error ? error.message : "Please try again later."}
          </p>
        </div>
      ) : groups.length === 0 ? (
        <div className="rounded-lg border border-border p-8 text-center">
          <Bot className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No tasks found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            No agents have autonomous tasks configured.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {groups.map((group) => (
            <div key={group.agent_id}>
              {/* Agent Header */}
              <Link
                href={`/agent/${group.agent_slug || group.agent_id}/tasks`}
                className="flex items-center gap-3 mb-4 hover:opacity-80 transition-opacity"
              >
                {group.agent_image ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={getImageUrl(group.agent_image) ?? undefined}
                    alt={group.agent_name || group.agent_id}
                    className="h-8 w-8 rounded-full object-cover"
                  />
                ) : (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                <h2 className="text-lg font-semibold">
                  {group.agent_name || group.agent_id}
                </h2>
                <span className="text-sm text-muted-foreground">
                  ({group.tasks.length})
                </span>
              </Link>

              {/* Task Cards */}
              <div className="space-y-3 pl-11">
                {group.tasks.map((task) => (
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
                            <Badge
                              variant="secondary"
                              className="bg-blue-100 text-blue-800 hover:bg-blue-100"
                            >
                              Memory
                            </Badge>
                          )}
                          <TaskBadgeActions
                            enabled={task.enabled}
                            logsHref={buildTaskLogsPath(
                              group.agent_slug || group.agent_id,
                              task.id,
                            )}
                            onToggle={() =>
                              setActionTask({
                                task,
                                agentId: group.agent_id,
                                type: "toggle",
                              })
                            }
                          />
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" className="h-8 w-8 p-0">
                                <span className="sr-only">Open menu</span>
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() =>
                                  setActionTask({
                                    task,
                                    agentId: group.agent_id,
                                    type: "toggle",
                                  })
                                }
                              >
                                <Power className="mr-2 h-4 w-4" />
                                {task.enabled ? "Disable" : "Enable"}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() =>
                                  handleEditTask(group.agent_id, task)
                                }
                              >
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onClick={() =>
                                  setActionTask({
                                    task,
                                    agentId: group.agent_id,
                                    type: "delete",
                                  })
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
                            `Every ${task.minutes} minutes`
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
            </div>
          ))}
        </div>
      )}
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
        task={editingTask?.task ?? null}
        onSave={handleSaveTask}
      />
    </div>
  );
}
