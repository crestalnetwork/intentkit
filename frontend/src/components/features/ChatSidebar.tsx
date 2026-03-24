"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Plus,
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

interface ExtraNavLink {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

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
  hideNavLinks?: boolean;
  extraNavLinks?: ExtraNavLink[];
}

type ThreadGroupKey = "today" | "yesterday" | "7days" | "30days" | "more";

const THREAD_GROUPS: Array<{ key: ThreadGroupKey; label: string }> = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "7days", label: "7days" },
  { key: "30days", label: "30days" },
  { key: "more", label: "More" },
];

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
  hideNavLinks,
  extraNavLinks,
}: ChatSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [tooltipThreadId, setTooltipThreadId] = useState<string | null>(null);
  const tooltipTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  const clearTooltipTimer = () => {
    if (!tooltipTimerRef.current) return;
    clearTimeout(tooltipTimerRef.current);
    tooltipTimerRef.current = null;
  };

  const handleTitleMouseEnter = (threadId: string, titleElement: HTMLSpanElement) => {
    clearTooltipTimer();
    setTooltipThreadId(null);
    if (titleElement.scrollWidth <= titleElement.clientWidth) return;
    tooltipTimerRef.current = setTimeout(() => {
      setTooltipThreadId(threadId);
    }, 1000);
  };

  const handleTitleMouseLeave = () => {
    clearTooltipTimer();
    setTooltipThreadId(null);
  };

  useEffect(() => {
    return () => {
      clearTooltipTimer();
    };
  }, []);

  const getThreadGroup = (dateStr: string): ThreadGroupKey => {
    const date = new Date(dateStr);
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dateStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diffDays = Math.floor((todayStart.getTime() - dateStart.getTime()) / 86400000);

    if (diffDays <= 0) return "today";
    if (diffDays === 1) return "yesterday";
    if (diffDays <= 7) return "7days";
    if (diffDays <= 30) return "30days";
    return "more";
  };

  const groupedThreads = useMemo(() => {
    const groups: Record<ThreadGroupKey, ChatThread[]> = {
      today: [],
      yesterday: [],
      "7days": [],
      "30days": [],
      more: [],
    };
    const sortedThreads = [...threads].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );

    for (const thread of sortedThreads) {
      groups[getThreadGroup(thread.updated_at)].push(thread);
    }

    return groups;
  }, [threads]);

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

      {/* Extra Navigation Links */}
      {extraNavLinks && extraNavLinks.length > 0 && (
        <>
          <div className="px-3 pb-3 space-y-1">
            {extraNavLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors hover:bg-muted text-muted-foreground hover:text-foreground"
              >
                <link.icon className="h-4 w-4" />
                {link.label}
              </Link>
            ))}
          </div>
          <div className="border-t mx-3 mb-2" />
        </>
      )}

      {/* Navigation Links */}
      {!hideNavLinks && (
        <>
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
        </>
      )}

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
                  "px-3 py-2 rounded-md text-sm truncate",
                  "bg-primary/10 text-primary font-medium",
                )}
              >
                New Chat
              </div>
            )}

            {/* Thread list */}
            {THREAD_GROUPS.map((group) => {
              const groupThreads = groupedThreads[group.key];
              if (groupThreads.length === 0) return null;

              return (
                <div key={group.key} className="space-y-1">
                  <div className="px-3 pt-2 pb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/80">
                    {group.label}
                  </div>
                  {groupThreads.map((thread) => (
                    <div
                      key={thread.id}
                      className={cn(
                        "group relative flex items-center px-3 py-2 rounded-md text-sm cursor-pointer transition-colors",
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
                            className="relative flex-1 min-w-0"
                            onClick={() => {
                              setTooltipThreadId(null);
                              onSelectThread(thread.id);
                            }}
                          >
                            <span
                              className="block truncate"
                              onMouseEnter={(e) =>
                                handleTitleMouseEnter(thread.id, e.currentTarget)
                              }
                              onMouseLeave={handleTitleMouseLeave}
                            >
                              {thread.summary || "Untitled"}
                            </span>
                            {tooltipThreadId === thread.id && (
                              <div className="pointer-events-none absolute left-0 top-full z-20 mt-1 max-w-[260px] rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md">
                                {thread.summary || "Untitled"}
                              </div>
                            )}
                          </div>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                size="icon"
                                variant="ghost"
                                className="absolute right-2 top-1/2 h-6 w-6 -translate-y-1/2 bg-background/80 backdrop-blur-sm opacity-0 pointer-events-none transition-opacity group-hover:opacity-100 group-hover:pointer-events-auto data-[state=open]:opacity-100 data-[state=open]:pointer-events-auto"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setTooltipThreadId(null);
                                }}
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
              );
            })}
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
