"use client";

import { useState } from "react";
import { Eye, Pencil } from "lucide-react";

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { Textarea } from "@/components/ui/textarea";
import type { Memory } from "@/types/memory";

// Keep in sync with MAX_MEMORY_BYTES in the backend (intentkit/core/memory.py)
const MAX_MEMORY_BYTES = 4000;

function byteLength(text: string): number {
  return new TextEncoder().encode(text).length;
}

function memoryTitle(memory: Memory): string {
  return memory.agent_name || memory.agent_id;
}

function ViewDialog({
  memory,
  onClose,
}: {
  memory: Memory;
  onClose: () => void;
}) {
  return (
    <AlertDialog open onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>{memoryTitle(memory)}</AlertDialogTitle>
          <AlertDialogDescription>
            Last updated {new Date(memory.updated_at).toLocaleString()}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="rounded-md border bg-muted/30 p-4">
          <MarkdownRenderer className="prose prose-sm prose-neutral dark:prose-invert max-w-none">
            {memory.content}
          </MarkdownRenderer>
        </div>
        <AlertDialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function EditDialog({
  memory,
  onSave,
  onClose,
}: {
  memory: Memory;
  onSave: (memory: Memory, content: string) => Promise<void>;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(memory.content ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bytes = byteLength(draft);
  const tooLong = bytes > MAX_MEMORY_BYTES;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(memory, draft);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save memory");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AlertDialog open onOpenChange={(open) => !open && !saving && onClose()}>
      <AlertDialogContent className="sm:max-w-[640px]">
        <AlertDialogHeader>
          <AlertDialogTitle>Edit {memoryTitle(memory)}</AlertDialogTitle>
          <AlertDialogDescription>
            This memory is managed automatically by the agent. Only edit it if
            you know exactly what you are doing — your changes may be merged
            with new information later.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={14}
          disabled={saving}
          aria-label="Memory content"
          className="font-mono text-xs"
        />
        <div className="flex items-center justify-between text-xs">
          <span className={tooLong ? "text-destructive" : "text-muted-foreground"}>
            {bytes} / {MAX_MEMORY_BYTES} bytes
          </span>
          {error && (
            <span role="alert" className="text-destructive">
              {error}
            </span>
          )}
        </div>
        <AlertDialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            disabled={saving || tooLong || draft === memory.content}
          >
            {saving ? "Saving..." : "Save"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function MemoryCard({
  memory,
  onView,
  onEdit,
}: {
  memory: Memory;
  onView: () => void;
  onEdit: () => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base truncate" title={memoryTitle(memory)}>
            {memoryTitle(memory)}
          </CardTitle>
          <div className="flex shrink-0 gap-1">
            <Button variant="ghost" size="sm" onClick={onView}>
              <Eye className="mr-1 h-3.5 w-3.5" />
              View
            </Button>
            <Button variant="ghost" size="sm" onClick={onEdit}>
              <Pencil className="mr-1 h-3.5 w-3.5" />
              Edit
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Updated {new Date(memory.updated_at).toLocaleString()}
        </p>
      </CardHeader>
      <CardContent>
        <p className="line-clamp-4 whitespace-pre-wrap text-sm text-muted-foreground">
          {memory.content.trim() || "(empty)"}
        </p>
      </CardContent>
    </Card>
  );
}

function MemoryGroup({
  title,
  description,
  memories,
  emptyText,
  onView,
  onEdit,
}: {
  title: string;
  description: string;
  memories: Memory[];
  emptyText: string;
  onView: (memory: Memory) => void;
  onEdit: (memory: Memory) => void;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {memories.length === 0 ? (
        <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
          {emptyText}
        </p>
      ) : (
        <div className="space-y-3">
          {memories.map((memory) => (
            <MemoryCard
              key={memory.id}
              memory={memory}
              onView={() => onView(memory)}
              onEdit={() => onEdit(memory)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export function MemorySections({
  memories,
  onSave,
}: {
  memories: Memory[];
  onSave: (memory: Memory, content: string) => Promise<void>;
}) {
  const [viewing, setViewing] = useState<Memory | null>(null);
  const [editing, setEditing] = useState<Memory | null>(null);

  const teamMemories = memories.filter((m) => m.scope === "team");
  const userMemories = memories.filter((m) => m.scope === "user");

  return (
    <div className="space-y-8">
      <MemoryGroup
        title="Team Memory"
        description="What each agent remembers for the whole team."
        memories={teamMemories}
        emptyText="No team memories yet. Agents create them automatically as your team works with them."
        onView={setViewing}
        onEdit={setEditing}
      />
      <MemoryGroup
        title="Your Memory"
        description="What each agent remembers about you personally."
        memories={userMemories}
        emptyText="No personal memories yet. Agents create them automatically as you chat with them."
        onView={setViewing}
        onEdit={setEditing}
      />
      {viewing && (
        <ViewDialog memory={viewing} onClose={() => setViewing(null)} />
      )}
      {editing && (
        <EditDialog
          memory={editing}
          onSave={onSave}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
