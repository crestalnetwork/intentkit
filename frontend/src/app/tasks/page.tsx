"use client";

import { useState } from "react";
import Link from "next/link";
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
import { TaskDialog } from "@/app/tasks/TaskDialog";
import { TargetAgentLabel } from "@/app/tasks/TargetAgentLabel";

export default function AllTasksPage() {
  const {
    data: tasks = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["all-tasks"],
    queryFn: () => autonomousApi.listTasks(),
  });

  const [actionTask, setActionTask] = useState<{
    task: AutonomousTask;
    type: "toggle" | "delete";
  } | null>(null);

  const [isTaskDialogOpen, setIsTaskDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<AutonomousTask | null>(null);

  const handleNewTask = () => {
    setEditingTask(null);
    setIsTaskDialogOpen(true);
  };

  const handleEditTask = (task: AutonomousTask) => {
    setEditingTask(task);
    setIsTaskDialogOpen(true);
  };

  const handleSaveTask = async (taskData: Partial<AutonomousTask>) => {
    try {
      if (editingTask) {
        await autonomousApi.updateTask(editingTask.id, taskData);
      } else {
        await autonomousApi.createTask(
          taskData as Omit<AutonomousTask, "id" | "chat_id">,
        );
      }
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
        await autonomousApi.updateTask(actionTask.task.id, {
          enabled: !actionTask.task.enabled,
        });
      } else if (actionTask.type === "delete") {
        await autonomousApi.deleteTask(actionTask.task.id);
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
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Tasks</h1>
            <p className="text-muted-foreground mt-2">
              Autonomous tasks scheduled for your team.
            </p>
          </div>
          <Button onClick={handleNewTask}>
            <Plus className="mr-2 h-4 w-4" />
            New Task
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-32 bg-muted animate-pulse rounded-md" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
            <p className="font-medium">Error loading tasks</p>
            <p className="text-sm mt-1">
              {error instanceof Error
                ? error.message
                : "Please try again later."}
            </p>
          </div>
        ) : tasks.length === 0 ? (
          <div className="rounded-lg border border-border p-8 text-center">
            <Bot className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No tasks found</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Your team has no autonomous tasks configured.
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
                    <div>
                      <span className="font-semibold text-muted-foreground">
                        Target Agent:{" "}
                      </span>
                      <TargetAgentLabel
                        targetAgentId={task.target_agent_id}
                        targetAgent={task.target_agent}
                      />
                    </div>
                    {task.created_by && task.created_by !== "system" && (
                      <div>
                        <span className="font-semibold text-muted-foreground">
                          Created by:{" "}
                        </span>
                        <span className="font-mono">{task.created_by}</span>
                      </div>
                    )}
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
      />
    </div>
  );
}
