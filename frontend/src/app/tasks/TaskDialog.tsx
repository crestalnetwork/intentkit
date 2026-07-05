import { useState } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AutonomousTask } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TaskDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  task?: AutonomousTask | null;
  onSave: (task: Partial<AutonomousTask>) => Promise<void>;
  // Pre-fill the target agent when creating a new task (e.g. from an agent page).
  defaultTargetAgentId?: string;
}

function buildFormData(
  task: AutonomousTask | null | undefined,
  defaultTargetAgentId: string | undefined,
): Partial<AutonomousTask> {
  if (task) {
    return {
      name: task.name || "",
      description: task.description || "",
      cron: task.cron || "",
      prompt: task.prompt || "",
      enabled: task.enabled,
      target_agent_id: task.target_agent_id || "",
    };
  }
  return {
    name: "",
    description: "",
    cron: "0 0 * * *",
    prompt: "",
    enabled: true,
    target_agent_id: defaultTargetAgentId || "",
  };
}

export function TaskDialog({
  open,
  onOpenChange,
  task,
  onSave,
  defaultTargetAgentId,
}: TaskDialogProps) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<Partial<AutonomousTask>>(() =>
    buildFormData(task, defaultTargetAgentId),
  );

  // Reset the form whenever the dialog (re)opens or its target task changes.
  // Tracking the inputs and syncing during render (instead of in an effect)
  // keeps the form in step without an extra commit + cascading render.
  const [synced, setSynced] = useState({ task, open, defaultTargetAgentId });
  if (
    synced.task !== task ||
    synced.open !== open ||
    synced.defaultTargetAgentId !== defaultTargetAgentId
  ) {
    setSynced({ task, open, defaultTargetAgentId });
    setFormData(buildFormData(task, defaultTargetAgentId));
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Normalize an empty target agent to null (lead-orchestrated).
      const payload: Partial<AutonomousTask> = {
        ...formData,
        target_agent_id: formData.target_agent_id?.trim()
          ? formData.target_agent_id
          : null,
      };
      await onSave(payload);
      onOpenChange(false);
    } catch (error) {
      console.error("Failed to save task:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {task ? "Edit Autonomous Task" : "New Autonomous Task"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              Configure the schedule and prompt for this autonomous team task.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <label htmlFor="name" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Name
              </label>
              <Input
                id="name"
                value={formData.name || ""}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="e.g. Daily News Summary"
              />
            </div>

            <div className="grid gap-2">
              <label htmlFor="description" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Description
              </label>
              <Input
                id="description"
                value={formData.description || ""}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Brief description of what this task does"
              />
            </div>

            <div className="grid gap-2">
              <label htmlFor="cron" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Cron Schedule <span className="text-destructive">*</span>
              </label>
              <div className="flex gap-2">
                <Input
                  id="cron"
                  value={formData.cron || ""}
                  onChange={(e) =>
                    setFormData({ ...formData, cron: e.target.value })
                  }
                  required
                  placeholder="0 0 * * *"
                  className="font-mono"
                />
              </div>
              <p className="text-[0.8rem] text-muted-foreground">
                Format: Minute Hour Day Month DayOfWeek (e.g., &quot;0 0 * * *&quot; for daily at midnight)
              </p>
            </div>

            <div className="grid gap-2">
              <label htmlFor="target_agent_id" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Target Agent (optional)
              </label>
              <Input
                id="target_agent_id"
                value={formData.target_agent_id || ""}
                onChange={(e) =>
                  setFormData({ ...formData, target_agent_id: e.target.value })
                }
                placeholder="Leave empty to let the team lead decide"
                className="font-mono"
              />
              <p className="text-[0.8rem] text-muted-foreground">
                When set, the task runs directly on that agent. Otherwise the
                team lead reads the prompt and delegates.
              </p>
            </div>

            <div className="grid gap-2">
              <label htmlFor="prompt" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Trigger Prompt <span className="text-destructive">*</span>
              </label>
              <textarea
                id="prompt"
                value={formData.prompt || ""}
                onChange={(e) =>
                  setFormData({ ...formData, prompt: e.target.value })
                }
                required
                className={cn(
                  "flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
                )}
                placeholder="Instructions for the agent to execute..."
              />
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="enabled"
                checked={formData.enabled}
                onChange={(e) =>
                  setFormData({ ...formData, enabled: e.target.checked })
                }
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <label
                htmlFor="enabled"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Enabled
              </label>
            </div>
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel type="button" disabled={loading}>Cancel</AlertDialogCancel>
            <Button type="submit" disabled={loading}>
              {loading ? "Saving..." : "Save"}
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}
