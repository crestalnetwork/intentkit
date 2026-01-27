import { useEffect, useState } from "react";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AutonomousTask } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TaskDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  task?: AutonomousTask | null;
  onSave: (task: Partial<AutonomousTask>) => Promise<void>;
}

export function TaskDialog({
  open,
  onOpenChange,
  task,
  onSave,
}: TaskDialogProps) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<Partial<AutonomousTask>>({
    name: "",
    description: "",
    cron: "0 * * * *", // default hourly
    prompt: "",
    enabled: false,
    has_memory: true,
  });

  useEffect(() => {
    if (task) {
      setFormData({
        name: task.name || "",
        description: task.description || "",
        cron: task.cron || "",
        prompt: task.prompt || "",
        enabled: task.enabled,
        has_memory: task.has_memory,
      });
    } else {
      setFormData({
        name: "",
        description: "",
        cron: "0 * * * *",
        prompt: "",
        enabled: false, // Default to disabled for safety
        has_memory: true,
      });
    }
  }, [task, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onSave(formData);
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
              Configure the schedule and prompt for this autonomous agent task.
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
                  placeholder="* * * * *"
                  className="font-mono"
                />
              </div>
              <p className="text-[0.8rem] text-muted-foreground">
                Format: Minute Hour Day Month DayOfWeek (e.g., "0 9 * * *" for daily at 9am)
              </p>
            </div>

            <div className="grid gap-2">
              <label htmlFor="prompt" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                System Prompt <span className="text-destructive">*</span>
              </label>
              <textarea
                id="prompt"
                value={formData.prompt || ""}
                onChange={(e) =>
                  setFormData({ ...formData, prompt: e.target.value })
                }
                required
                className={cn(
                  "flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
                )}
                placeholder="Instructions for the agent to execute..."
              />
            </div>

            <div className="flex items-center gap-4">
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

              <div className="flex items-center space-x-2">
                 <input
                  type="checkbox"
                  id="has_memory"
                  checked={formData.has_memory}
                  onChange={(e) =>
                    setFormData({ ...formData, has_memory: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                />
                <label
                  htmlFor="has_memory"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Enable Memory
                </label>
              </div>
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
