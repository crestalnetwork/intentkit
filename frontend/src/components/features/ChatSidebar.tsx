"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Plus,
  MessageSquare,
  MoreVertical,
  Pencil,
  Trash2,
  Check,
  X,
  Activity,
  FileText,
  ListTodo,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { cn } from "@/lib/utils";
import type { ChatThread } from "@/types/chat";

interface ChatSidebarProps {
  agentId: string;
  activeTab?: "chat" | "activities" | "posts" | "tasks";
  threads: ChatThread[];
  currentThreadId: string | null;
  isNewThread: boolean;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onUpdateTitle: (threadId: string, title: string) => Promise<void>;
  onDeleteThread: (threadId: string) => Promise<void>;
  isLoading?: boolean;
}

export function ChatSidebar({
  agentId,
  activeTab = "chat",
  threads,
  currentThreadId,
  isNewThread,
  onSelectThread,
  onNewThread,
  onUpdateTitle,
  onDeleteThread,
  isLoading,
}: ChatSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const handleStartEdit = (thread: ChatThread) => {
    setEditingId(thread.id);
    setEditValue(thread.summary || "");
  };

  const handleSaveEdit = async () => {
    if (!editingId || !editValue.trim()) return;
    setIsSavingEdit(true);
    try {
      await onUpdateTitle(editingId, editValue.trim());
      setEditingId(null);
      setEditValue("");
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue("");
  };

  const handleConfirmDelete = async () => {
    if (!deleteId) return;
    setIsDeleting(true);
    try {
      await onDeleteThread(deleteId);
      setDeleteId(null);
    } finally {
      setIsDeleting(false);
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } else if (diffDays === 1) {
      return "Yesterday";
    } else if (diffDays < 7) {
      return date.toLocaleDateString([], { weekday: "short" });
    } else {
      return date.toLocaleDateString([], { month: "short", day: "numeric" });
    }
  };

  return (
    <div className="w-64 border-r bg-muted/30 flex flex-col h-full">
      {/* New Chat Button */}
      <div className="p-3">
        <Button
          onClick={onNewThread}
          className="w-full justify-start gap-2"
          variant="outline"
        >
          <Plus className="h-4 w-4" />
          New Chat Thread
        </Button>
      </div>

      {/* Navigation Links */}
      <div className="px-3 pb-3 space-y-1">
        <Link
          href={`/agent/${agentId}/tasks`}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
            activeTab === "tasks"
              ? "bg-primary/10 text-primary font-medium"
              : "hover:bg-muted text-muted-foreground hover:text-foreground"
          )}
        >
          <ListTodo className="h-4 w-4" />
          Tasks
        </Link>
        <Link
          href={`/agent/${agentId}/activities`}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
            activeTab === "activities"
              ? "bg-primary/10 text-primary font-medium"
              : "hover:bg-muted text-muted-foreground hover:text-foreground"
          )}
        >
          <Activity className="h-4 w-4" />
          Activities
        </Link>
        <Link
          href={`/agent/${agentId}/posts`}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
            activeTab === "posts"
              ? "bg-primary/10 text-primary font-medium"
              : "hover:bg-muted text-muted-foreground hover:text-foreground"
          )}
        >
          <FileText className="h-4 w-4" />
          Posts
        </Link>
      </div>

      {/* Separator */}
      <div className="border-t mx-3 mb-2" />

      {/* Thread List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-muted animate-pulse rounded-md" />
            ))}
          </div>
        ) : threads.length === 0 && !isNewThread ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            No chat history
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {/* Show "New Chat" placeholder if in new thread mode */}
            {isNewThread && (
              <div
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
                  "bg-primary/10 text-primary font-medium",
                )}
              >
                <MessageSquare className="h-4 w-4" />
                <span className="flex-1 truncate">New Chat</span>
              </div>
            )}

            {/* Thread list */}
            {threads.map((thread) => (
              <div
                key={thread.id}
                className={cn(
                  "group flex items-center gap-2 px-3 py-2 rounded-md text-sm cursor-pointer transition-colors",
                  currentThreadId === thread.id && !isNewThread
                    ? "bg-primary/10 text-primary font-medium"
                    : "hover:bg-muted",
                )}
              >
                {editingId === thread.id ? (
                  <div className="flex-1 flex items-center gap-1">
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="h-7 text-xs"
                      autoFocus
                      onKeyDown={(e) => {
                        // Check if IME is composing before handling Enter key
                        if (e.nativeEvent.isComposing) return;
                        if (e.key === "Enter") handleSaveEdit();
                        if (e.key === "Escape") handleCancelEdit();
                      }}
                      disabled={isSavingEdit}
                    />
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6"
                      onClick={handleSaveEdit}
                      disabled={isSavingEdit}
                    >
                      <Check className="h-3 w-3" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6"
                      onClick={handleCancelEdit}
                      disabled={isSavingEdit}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ) : (
                  <>
                    <div
                      className="flex-1 min-w-0 flex items-center gap-2"
                      onClick={() => onSelectThread(thread.id)}
                    >
                      <MessageSquare className="h-4 w-4 shrink-0" />
                      <span className="flex-1 truncate">
                        {thread.summary || "Untitled"}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {formatTime(thread.updated_at)}
                    </span>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 opacity-0 group-hover:opacity-100"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreVertical className="h-3 w-3" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleStartEdit(thread)}>
                          <Pencil className="mr-2 h-4 w-4" />
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDeleteId(thread.id)}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chat Thread</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this chat? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
