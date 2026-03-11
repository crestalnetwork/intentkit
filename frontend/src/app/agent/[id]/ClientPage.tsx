"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Send,
  Bot,
  User,
  ArrowLeft,
  Pencil,
  Info,
  AlertCircle,
  MoreVertical,
  Archive,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  cacheAgentAvatar,
  getCachedAgentAvatar,
  getImageUrl,
} from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
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
import { agentApi, chatApi } from "@/lib/api";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { SkillCallBadgeList } from "@/components/features/SkillCallBadge";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { toast } from "@/hooks/use-toast";
import { isUserAuthoredMessage } from "@/types/chat";
import type { UIMessage, ChatThread, ChatMessage } from "@/types/chat";
import { buildChatThreadPath } from "@/lib/autonomousChat";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

// Tailwind prose classes for markdown rendering in chat bubbles
const markdownProseClass =
  "prose prose-sm dark:prose-invert max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0";

// Check if a thread is older than 3 days
function isThreadOlderThanThreeDays(thread: ChatThread): boolean {
  const updatedAt = new Date(thread.updated_at);
  const threeDaysAgo = new Date();
  threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
  return updatedAt < threeDaysAgo;
}

// Convert API ChatMessage to UI message
function apiMessageToUIMessage(msg: ChatMessage): UIMessage {
  const isUserMessage = isUserAuthoredMessage(msg.author_type);
  return {
    id: msg.id,
    role: isUserMessage ? "user" : "agent",
    content: msg.message,
    timestamp: new Date(msg.created_at),
    skillCalls: msg.skill_calls,
    attachments: msg.attachments,
  };
}

// Check if message has non-xmtp attachments (UI attachments)
function hasUIAttachments(msg: UIMessage): boolean {
  return (
    !!msg.attachments &&
    msg.attachments.some((a) => a.type === "card" || a.type === "choice")
  );
}

// Option key to label mapping
const optionLabels: Record<string, string> = { a: "A.", b: "B.", c: "C." };

// Card attachment component
function CardAttachment({
  att,
}: {
  att: import("@/types/chat").ChatMessageAttachment;
}) {
  const json = att.json as Record<string, string> | undefined;
  const isClickable = !!att.url;
  const card = (
    <div
      className={cn(
        "border rounded-lg max-w-sm bg-white dark:bg-zinc-900 transition-shadow",
        isClickable && "hover:shadow-md cursor-pointer",
      )}
    >
      {json?.image_url && (
        <img
          src={json.image_url}
          alt={json?.title || "Card image"}
          className="w-full h-40 object-cover rounded-t-lg"
        />
      )}
      <div className="p-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="font-medium text-sm">{json?.title}</h4>
          {json?.label && (
            <span className="shrink-0 text-xs text-primary bg-primary/10 rounded px-2 py-0.5">
              {json.label}
            </span>
          )}
        </div>
        {json?.description && (
          <p className="text-xs text-muted-foreground mt-1">
            {json.description}
          </p>
        )}
      </div>
    </div>
  );
  if (isClickable) {
    const url = att.url!;
    const isExternal =
      url.startsWith("http://") || url.startsWith("https://")
        ? new URL(url).origin !== window.location.origin
        : false;
    return (
      <a
        href={url}
        {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      >
        {card}
      </a>
    );
  }
  return card;
}

// Choice attachment component
function ChoiceAttachment({
  att,
  onSendMessage,
}: {
  att: import("@/types/chat").ChatMessageAttachment;
  onSendMessage: (message: string) => void;
}) {
  const options = att.json as Record<
    string,
    { title: string; content: string }
  > | null;
  if (!options) return null;
  return (
    <div className="space-y-2">
      {Object.entries(options).map(([key, opt]) => (
        <button
          key={key}
          className="w-full text-left border rounded-lg p-3 bg-white dark:bg-zinc-900 hover:shadow-md transition-shadow cursor-pointer"
          onClick={() => onSendMessage(opt.title)}
        >
          <div className="font-medium text-sm">
            {optionLabels[key] || `${key.toUpperCase()}.`} {opt.title}
          </div>
          <div className="text-xs text-muted-foreground">{opt.content}</div>
        </button>
      ))}
    </div>
  );
}

export default function AgentChatPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const agentId = params.id as string;

  const {
    data: agent,
    isLoading: isLoadingAgent,
    error: agentError,
  } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId),
    enabled: !!agentId,
  });

  // Thread state
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [isNewThread, setIsNewThread] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Message state
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Archive dialog
  const [showArchiveDialog, setShowArchiveDialog] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Fetch thread list
  const {
    data: threads = [],
    isLoading: isLoadingThreads,
    refetch: refetchThreads,
  } = useQuery({
    queryKey: ["chats", agentId],
    queryFn: () => chatApi.listChats(agentId),
    enabled: !!agentId,
  });

  // Initialize: select the most recent thread or start new if older than 3 days
  useEffect(() => {
    if (!agentId) return;

    // Do not let URL changes reset state while we are sending a message
    // because Next.js router transitions may cause searchParams to lag behind local state
    if (isSending) return;

    // Handle explicit new thread from URL
    if (searchParams.get("new") === "true") {
      if (!isNewThread) {
        setIsNewThread(true);
        setCurrentThreadId(null);
        setMessages([]);
      }
      setHasInitialized(true);
      return;
    }

    const threadFromUrl = searchParams.get("thread");
    if (threadFromUrl) {
      if (currentThreadId !== threadFromUrl || isNewThread) {
        setCurrentThreadId(threadFromUrl);
        setIsNewThread(false);
      }
      setHasInitialized(true);
      return;
    }

    if (hasInitialized || isLoadingThreads) return;

    if (threads.length === 0) {
      // No threads, start a new one
      setIsNewThread(true);
      setCurrentThreadId(null);
    } else {
      // Sort by updated_at descending and pick the first
      const sorted = [...threads].sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      );
      const mostRecent = sorted[0];

      if (isThreadOlderThanThreeDays(mostRecent)) {
        // Most recent thread is older than 3 days, start new
        setIsNewThread(true);
        setCurrentThreadId(null);
      } else {
        // Use the most recent thread
        setCurrentThreadId(mostRecent.id);
        setIsNewThread(false);
        router.replace(buildChatThreadPath(agentId, mostRecent.id));
      }
    }
    setHasInitialized(true);
  }, [
    threads,
    isLoadingThreads,
    hasInitialized,
    agentId,
    searchParams,
    currentThreadId,
    isNewThread,
    router,
    isSending,
  ]);

  useEffect(() => {
    if (!agentId) return;
    cacheAgentAvatar(agentId, agent?.picture);
  }, [agentId, agent?.picture]);

  // Load messages when thread changes (but not during send operation)
  useEffect(() => {
    // Don't load messages while sending - this prevents overwriting the user's message
    // that was just added to state when we switch from isNewThread to an actual thread
    if (isSending) return;

    if (!currentThreadId || !agentId || isNewThread) {
      setMessages([]);
      return;
    }

    const loadMessages = async () => {
      try {
        const response = await chatApi.listMessages(agentId, currentThreadId);
        // API returns messages in DESC order, reverse for chronological display
        const uiMessages = response.data.reverse().map(apiMessageToUIMessage);
        setMessages(uiMessages);
      } catch (err) {
        console.error("Failed to load messages:", err);
        setError("Failed to load message history");
      }
    };

    loadMessages();
  }, [currentThreadId, agentId, isNewThread, isSending]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Thread actions
  const handleSelectThread = useCallback(
    (threadId: string) => {
      setError(null);
      router.push(buildChatThreadPath(agentId, threadId));
    },
    [agentId, router],
  );

  const handleNewThread = useCallback(() => {
    router.push(`/agent/${agentId}?new=true`);
  }, [agentId, router]);

  const handleUpdateTitle = useCallback(
    async (threadId: string, title: string) => {
      if (!agentId) return;
      await chatApi.updateChatSummary(agentId, threadId, title);
      await refetchThreads();
    },
    [agentId, refetchThreads],
  );

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      if (!agentId) return;
      await chatApi.deleteChat(agentId, threadId);
      await refetchThreads();

      // If we deleted the current thread, switch to another or start new
      if (currentThreadId === threadId) {
        const remaining = threads.filter((t) => t.id !== threadId);
        if (remaining.length > 0) {
          const sorted = [...remaining].sort(
            (a, b) =>
              new Date(b.updated_at).getTime() -
              new Date(a.updated_at).getTime(),
          );
          router.replace(buildChatThreadPath(agentId, sorted[0].id));
        } else {
          setMessages([]);
          router.replace(`/agent/${agentId}?new=true`);
        }
      }
    },
    [agentId, refetchThreads, currentThreadId, threads, router],
  );

  // Send message with streaming
  const handleSendMessage = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!inputValue.trim() || isSending || !agentId) return;

      const userMessage: UIMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: inputValue,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setInputValue("");
      setIsSending(true);
      setError(null);

      try {
        let threadId = currentThreadId;

        // If this is a new thread, create it first
        if (isNewThread || !threadId) {
          const newThread = await chatApi.createChat(
            agentId,
            undefined,
            userMessage.content,
          );
          threadId = newThread.id;
          setCurrentThreadId(threadId);
          setIsNewThread(false);
          await refetchThreads();
          router.replace(buildChatThreadPath(agentId, threadId));
        }

        // Stream the response
        for await (const msg of chatApi.sendMessageStream(
          agentId,
          threadId,
          userMessage.content,
        )) {
          const uiMsg = apiMessageToUIMessage(msg);
          setMessages((prev) => {
            // Check if message already exists (by id)
            const existing = prev.find((m) => m.id === uiMsg.id);
            if (existing) {
              return prev.map((m) => (m.id === uiMsg.id ? uiMsg : m));
            }
            return [...prev, uiMsg];
          });
        }

        // Refetch threads to update the summary/timestamp
        await refetchThreads();
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to send message";
        setError(errorMessage);
        // Remove the user message on error
        setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
      } finally {
        setIsSending(false);
      }
    },
    [
      inputValue,
      isSending,
      agentId,
      currentThreadId,
      isNewThread,
      refetchThreads,
      router,
    ],
  );

  // Send a text message programmatically (used by choice buttons)
  const sendTextMessage = useCallback(
    (text: string) => {
      setInputValue(text);
      // Use setTimeout to ensure state is updated before triggering send
      setTimeout(() => {
        const form = document.querySelector(
          "form",
        ) as HTMLFormElement | null;
        form?.requestSubmit();
      }, 0);
    },
    [],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    // Check if IME is composing (e.g., inputting Chinese characters)
    // When isComposing is true, Enter is used to confirm IME selection, not to send message
    if (e.nativeEvent.isComposing) return;

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (!agentId) {
    return (
      <div className="container py-10">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">No agent ID provided</p>
          <p className="text-sm mt-1">
            Please go back and select an agent to chat with.
          </p>
          <Button asChild variant="outline" className="mt-4">
            <Link href="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Agents
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  if (isLoadingAgent) {
    return (
      <div className="container py-10">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-1/3 bg-muted rounded" />
          <div className="h-[500px] bg-muted rounded" />
        </div>
      </div>
    );
  }

  if (agentError || !agent) {
    return (
      <div className="container py-10">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Error loading agent</p>
          <p className="text-sm mt-1">
            {agentError instanceof Error
              ? agentError.message
              : "Agent not found"}
          </p>
          <Button asChild variant="outline" className="mt-4">
            <Link href="/">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Agents
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const displayName = agent.name || agent.id;
  const cachedAvatar = getCachedAgentAvatar(agentId) ?? getImageUrl(agent.picture);

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar */}
      <ChatSidebar
        agentId={agentId}
        activeTab="chat"
        threads={threads}
        currentThreadId={currentThreadId}
        isNewThread={isNewThread}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onUpdateTitle={handleUpdateTitle}
        onDeleteThread={handleDeleteThread}
        isLoading={isLoadingThreads}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col p-6">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <Link
            href={`/agent/${agentId}/activities`}
            className="flex items-center gap-3"
          >
            <Avatar className="h-10 w-10">
              {cachedAvatar ? (
                <AvatarImage src={cachedAvatar} alt={displayName} />
              ) : null}
              <AvatarFallback className="bg-primary/10">
                <Bot className="h-5 w-5 text-primary" />
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="text-xl font-bold">{displayName}</h1>
              <p className="text-sm text-muted-foreground line-clamp-1">
                {agent.purpose || "No description"}
              </p>
            </div>
          </Link>
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
                <DropdownMenuItem
                  onClick={() => setShowArchiveDialog(true)}
                  className="text-destructive focus:text-destructive"
                >
                  <Archive className="mr-2 h-4 w-4" />
                  Archive
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Archive Confirmation Dialog */}
            <AlertDialog
              open={showArchiveDialog}
              onOpenChange={setShowArchiveDialog}
            >
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Archive Agent</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to archive this agent? Archived agents
                    will be hidden from the agent list.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={isArchiving}>
                    Cancel
                  </AlertDialogCancel>
                  <AlertDialogAction
                    disabled={isArchiving}
                    onClick={async (e) => {
                      e.preventDefault();
                      setIsArchiving(true);
                      try {
                        await agentApi.archive(agentId);
                        await queryClient.invalidateQueries({
                          queryKey: ["agents"],
                        });
                        toast({
                          title: "Agent archived",
                          description: "The agent has been archived.",
                          variant: "success",
                        });
                        router.push("/");
                      } catch (err) {
                        toast({
                          title: "Error",
                          description:
                            err instanceof Error
                              ? err.message
                              : "Failed to archive agent",
                          variant: "destructive",
                        });
                        setShowArchiveDialog(false);
                      } finally {
                        setIsArchiving(false);
                      }
                    }}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {isArchiving ? "Archiving..." : "Archive"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>

        {/* Agent Info Bar */}
        <div className="mb-4 rounded-lg border bg-muted/50 p-3">
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Model:</span>
              <span className="font-mono text-xs bg-background px-2 py-0.5 rounded">
                {agent.model}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Agent ID:</span>
              <span className="font-mono text-xs bg-background px-2 py-0.5 rounded">
                {agent.id}
              </span>
            </div>
            {currentThreadId && (
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Chat ID:</span>
                <span className="font-mono text-xs bg-background px-2 py-0.5 rounded">
                  {currentThreadId}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 rounded-lg border border-destructive/50 bg-destructive/10 p-3 flex items-center gap-2 text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto"
              onClick={() => setError(null)}
            >
              Dismiss
            </Button>
          </div>
        )}

        {/* Chat Interface */}
        <Card className="flex-1 flex flex-col overflow-hidden">
          <CardHeader className="border-b py-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Bot className="h-4 w-4" />
              <span>
                {isNewThread
                  ? "New Chat"
                  : threads.find((t) => t.id === currentThreadId)?.summary ||
                  "Chat Session"}
              </span>
              <span className="text-xs">
                ({messages.length} message{messages.length !== 1 ? "s" : ""})
              </span>
            </div>
          </CardHeader>

          <CardContent
            className="flex-1 overflow-y-auto p-4 space-y-4"
            ref={scrollRef}
          >
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                <Bot className="h-12 w-12 mb-4 opacity-50" />
                <p className="text-lg font-medium">Start a conversation</p>
                <p className="text-sm">
                  Send a message to chat with {displayName}
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={cn(
                    "flex w-full gap-2 max-w-[85%]",
                    msg.role === "user" ? "ml-auto flex-row-reverse" : "",
                  )}
                >
                  {msg.role === "agent" ? (
                    <Avatar className="h-8 w-8 border">
                      {cachedAvatar ? (
                        <AvatarImage src={cachedAvatar} alt={displayName} />
                      ) : null}
                      <AvatarFallback className="bg-primary text-primary-foreground">
                        <Bot className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                  ) : (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-muted">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                  <div
                    className={cn(
                      "rounded-lg px-4 py-2 text-sm",
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground",
                    )}
                  >
                    {/* UI Attachments or Skill Call Badges */}
                    {hasUIAttachments(msg) ? (
                      <div className="space-y-2 mb-2">
                        {msg.attachments!
                          .filter(
                            (a) =>
                              a.type === "card" || a.type === "choice",
                          )
                          .map((att, i) => (
                            <div key={i}>
                              {att.lead_text && (
                                <p className="text-sm mt-2 mb-3">
                                  {att.lead_text}
                                </p>
                              )}
                              {att.type === "card" && (
                                <CardAttachment att={att} />
                              )}
                              {att.type === "choice" && (
                                <ChoiceAttachment
                                  att={att}
                                  onSendMessage={sendTextMessage}
                                />
                              )}
                            </div>
                          ))}
                      </div>
                    ) : (
                      msg.skillCalls &&
                      msg.skillCalls.length > 0 && (
                        <div className="mb-2">
                          <SkillCallBadgeList
                            skillCalls={msg.skillCalls}
                          />
                        </div>
                      )
                    )}

                    {/* Message Content */}
                    {msg.role === "agent" ? (
                      <MarkdownRenderer
                        className={markdownProseClass}
                        enableBreaks
                      >
                        {msg.content}
                      </MarkdownRenderer>
                    ) : (
                      <div className="whitespace-pre-wrap break-words">
                        {msg.content}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {isSending && (
              <div className="flex w-full gap-2 max-w-[85%]">
                <Avatar className="h-8 w-8 border">
                  {cachedAvatar ? (
                    <AvatarImage src={cachedAvatar} alt={displayName} />
                  ) : null}
                  <AvatarFallback className="bg-primary text-primary-foreground">
                    <Bot className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="flex items-center gap-1 rounded-lg bg-muted px-4 py-2">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.3s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.15s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50" />
                </div>
              </div>
            )}
          </CardContent>

          <div className="p-4 border-t bg-background">
            <form onSubmit={handleSendMessage} className="flex gap-2">
              <Input
                placeholder={
                  isSending ? "Waiting for response..." : "Type a message..."
                }
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1"
                autoFocus
              />
              <Button
                type="submit"
                disabled={isSending || !inputValue.trim()}
                title={
                  isSending ? "Please wait for the response" : "Send message"
                }
              >
                <Send className="h-4 w-4" />
                <span className="sr-only">Send</span>
              </Button>
            </form>
            {isSending && (
              <p className="text-xs text-muted-foreground mt-2 text-center">
                Processing your message...
              </p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
