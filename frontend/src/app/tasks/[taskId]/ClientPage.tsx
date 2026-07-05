"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import cronstrue from "cronstrue";
import {
  ArrowLeft,
  MoreHorizontal,
  Pencil,
  Power,
  Trash,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { autonomousApi, AutonomousTask } from "@/lib/api";
import { TaskDialog } from "@/app/tasks/TaskDialog";
import { TargetAgentLabel } from "@/app/tasks/TargetAgentLabel";
import { ExecutionsSection } from "./ExecutionsSection";

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = params.taskId as string;
  const router = useRouter();

  const {
    data: task,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => autonomousApi.getTask(taskId),
    enabled: !!taskId,
  });

  const [action, setAction] = useState<"toggle" | "delete" | null>(null);
  const [isTaskDialogOpen, setIsTaskDialogOpen] = useState(false);

  const handleSaveTask = async (taskData: Partial<AutonomousTask>) => {
    await autonomousApi.updateTask(taskId, taskData);
    refetch();
  };

  const handleConfirmAction = async () => {
    if (!action || !task) return;
    try {
      if (action === "toggle") {
        await autonomousApi.updateTask(taskId, { enabled: !task.enabled });
        refetch();
      } else if (action === "delete") {
        await autonomousApi.deleteTask(taskId);
        router.push("/tasks");
      }
    } catch (error) {
      console.error("Failed to perform action:", error);
    } finally {
      setAction(null);
    }
  };

  if (isLoading) {
    return (
      <div className="container py-10">
        <div className="mx-auto max-w-[768px] space-y-4">
          <div className="h-10 w-1/2 animate-pulse rounded-md bg-muted" />
          <div className="h-40 animate-pulse rounded-md bg-muted" />
        </div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="container py-10">
        <div className="mx-auto max-w-[768px]">
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
            <p className="font-medium">Error loading task</p>
            <p className="mt-1 text-sm">
              {error instanceof Error ? error.message : "Task not found."}
            </p>
          </div>
          <Button variant="outline" className="mt-4" asChild>
            <Link href="/tasks">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Tasks
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container py-10">
      <div className="mx-auto max-w-[768px]">
        <div className="mb-6 flex items-start justify-between">
          <div className="flex items-start gap-3">
            <Button variant="ghost" size="icon" asChild>
              <Link href="/tasks">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">
                {task.name || "Untitled Task"}
              </h1>
              <p className="mt-1 text-muted-foreground">
                {task.description || "No description provided"}
              </p>
            </div>
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
                <DropdownMenuItem onClick={() => setAction("toggle")}>
                  <Power className="mr-2 h-4 w-4" />
                  {task.enabled ? "Disable" : "Enable"}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setIsTaskDialogOpen(true)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setAction("delete")}
                >
                  <Trash className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
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
                <span className="mt-0.5 font-mono text-xs text-muted-foreground">
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
            <div className="mb-1 text-xs font-semibold text-muted-foreground">
              Prompt:
            </div>
            <div className="max-h-40 overflow-y-auto rounded-md bg-muted/50 p-3 font-mono text-xs whitespace-pre-wrap">
              {task.prompt}
            </div>
          </div>
        )}

        <ExecutionsSection taskId={taskId} />
      </div>

      <AlertDialog
        open={!!action}
        onOpenChange={(open) => !open && setAction(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              {action === "toggle"
                ? `This will ${task.enabled ? "disable" : "enable"} the task "${task.name ?? "Untitled"}".`
                : `This will permanently delete the task "${task.name ?? "Untitled"}" and its run history. This action cannot be undone.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmAction}>
              {action === "delete" ? "Delete" : "Confirm"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <TaskDialog
        open={isTaskDialogOpen}
        onOpenChange={setIsTaskDialogOpen}
        task={task}
        onSave={handleSaveTask}
      />
    </div>
  );
}
