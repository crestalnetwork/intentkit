"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bot, User } from "lucide-react";
import Link from "next/link";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { SkillCallBadgeList } from "@/components/features/SkillCallBadge";
import { ThinkingBlock } from "@/components/features/ThinkingBlock";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ImageAttachment } from "@/components/features/ImageAttachment";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { buildChatThreadPath, getAutonomousChatId } from "@/lib/autonomousChat";
import { agentApi, autonomousApi, chatApi } from "@/lib/api";
import { useAgentSlugRewrite } from "@/hooks/useAgentSlugRewrite";
import {
  cacheAgentAvatar,
  cn,
  getCachedAgentAvatar,
  getImageUrl,
} from "@/lib/utils";
import { isUserAuthoredMessage } from "@/types/chat";
import type { ChatMessage, UIMessage } from "@/types/chat";

const markdownProseClass =
  "prose prose-sm dark:prose-invert max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0";

function apiMessageToUIMessage(msg: ChatMessage): UIMessage {
  const isUserMessage = isUserAuthoredMessage(msg.author_type);
  return {
    id: msg.id,
    role: isUserMessage ? "user" : "agent",
    content: msg.message,
    thinking: msg.thinking,
    timestamp: new Date(msg.created_at),
    skillCalls: msg.skill_calls,
    attachments: msg.attachments,
  };
}

// Check if message has non-xmtp attachments (UI attachments)
function hasUIAttachments(msg: UIMessage): boolean {
  return (
    !!msg.attachments &&
    msg.attachments.some(
      (a) => a.type === "card" || a.type === "choice" || a.type === "image",
    )
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

export default function TaskLogsPage() {
  const params = useParams();
  const agentId = params.id as string;
  const taskId = params.taskId as string;
  const chatId = getAutonomousChatId(taskId);

  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasInitialized, setHasInitialized] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: agent, isLoading: isLoadingAgent } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId),
    enabled: !!agentId,
  });

  useAgentSlugRewrite(agentId, agent?.slug);

  // The real agent ID for API calls (agentId from params may be a slug after URL rewrite)
  const resolvedId = agent?.id;

  const {
    data: tasks = [],
    isLoading: isLoadingTasks,
  } = useQuery({
    queryKey: ["tasks", resolvedId],
    queryFn: () => autonomousApi.listTasks(resolvedId!),
    enabled: !!resolvedId,
  });

  const {
    data: threads = [],
    isLoading: isLoadingThreads,
    refetch: refetchThreads,
  } = useQuery({
    queryKey: ["chats", resolvedId],
    queryFn: () => chatApi.listChats(resolvedId!),
    enabled: !!resolvedId,
  });

  useEffect(() => {
    if (!agentId) return;
    cacheAgentAvatar(agentId, agent?.picture);
  }, [agentId, agent?.picture]);

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

  useEffect(() => {
    if (!agentId || !taskId || hasInitialized) return;
    setHasInitialized(true);
  }, [agentId, taskId, hasInitialized]);

  useEffect(() => {
    if (!resolvedId || !hasInitialized || isSending) return;

    const loadMessages = async () => {
      try {
        const response = await chatApi.listMessages(resolvedId, chatId);
        const uiMessages = response.data.reverse().map(apiMessageToUIMessage);
        setMessages(uiMessages);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to load logs";
        setError(errorMessage);
      }
    };

    loadMessages();
  }, [resolvedId, chatId, hasInitialized, isSending]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!inputValue.trim() || isSending || !resolvedId) return;

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
        for await (const msg of chatApi.sendMessageStream(
          resolvedId,
          chatId,
          userMessage.content,
        )) {
          const uiMsg = apiMessageToUIMessage(msg);
          setMessages((prev) => {
            const existing = prev.find((m) => m.id === uiMsg.id);
            if (existing) {
              return prev.map((m) => (m.id === uiMsg.id ? uiMsg : m));
            }
            return [...prev, uiMsg];
          });
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to send message";
        setError(errorMessage);
        setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
      } finally {
        setIsSending(false);
      }
    },
    [
      resolvedId,
      chatId,
      inputValue,
      isSending,
    ],
  );

  // Send a text message programmatically (used by choice buttons)
  const sendTextMessage = useCallback(
    (text: string) => {
      setInputValue(text);
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
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (!agentId || !taskId) {
    return (
      <div className="container py-10">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Missing agent or task</p>
          <p className="text-sm mt-1">
            Please go back and select an autonomous task.
          </p>
          <Button asChild variant="outline" className="mt-4">
            <Link href="/agents">
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

  const displayName = agent?.name || agent?.id || agentId;
  const cachedAvatar = getCachedAgentAvatar(agentId) ?? getImageUrl(agent?.picture);
  const task = tasks.find((item) => item.id === taskId);
  const sidebarThreads = threads.filter((thread) => thread.id !== chatId);

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      <ChatSidebar
        agentId={agentId}
        activeTab="tasks"
        threads={sidebarThreads}
        currentThreadId={chatId}
        isNewThread={false}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onUpdateTitle={handleUpdateTitle}
        onDeleteThread={handleDeleteThread}
        isLoading={isLoadingThreads}
        enableActivity={agent?.enable_activity !== false || agent?.enable_post !== false}
        enablePost={agent?.enable_post !== false}
      />
      <div className="flex-1 flex flex-col p-6 overflow-hidden">
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
                {agent?.purpose || "No description"}
              </p>
            </div>
          </Link>
          <div className="text-sm text-muted-foreground">
            {task?.name || "Task Logs"}
          </div>
        </div>

        <Card className="flex-1 flex flex-col overflow-hidden">
          <CardHeader className="border-b py-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Bot className="h-4 w-4" />
              <span>{task?.name || taskId}</span>
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
                <p className="text-lg font-medium">No logs yet</p>
                <p className="text-sm">
                  Messages from this task will appear here.
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
                    {/* Skill Call Badges and UI Attachments */}
                    {msg.skillCalls && msg.skillCalls.length > 0 && (
                      <div className="mb-2">
                        <SkillCallBadgeList skillCalls={msg.skillCalls} />
                      </div>
                    )}
                    {hasUIAttachments(msg) && (
                      <div className="space-y-2 mb-2">
                        {msg.attachments!
                          .filter(
                            (a) =>
                              a.type === "card" ||
                              a.type === "choice" ||
                              a.type === "image",
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
                              {att.type === "image" && (
                                <ImageAttachment att={att} />
                              )}
                            </div>
                          ))}
                      </div>
                    )}
                    {msg.thinking && <ThinkingBlock thinking={msg.thinking} />}
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
              />
              <Button type="submit" disabled={isSending || !inputValue.trim()}>
                Send
              </Button>
            </form>
            {error && (
              <div className="mt-2 text-sm text-destructive">{error}</div>
            )}
          </div>
        </Card>
        {isLoadingTasks && (
          <div className="mt-3 text-xs text-muted-foreground">
            Loading task details...
          </div>
        )}
      </div>
    </div>
  );
}
