"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Send,
  Square,
  Bot,
  User,
  AlertCircle,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { leadApi } from "@/lib/api";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { SkillCallBadgeList } from "@/components/features/SkillCallBadge";
import { ThinkingBlock } from "@/components/features/ThinkingBlock";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { ImageAttachment } from "@/components/features/ImageAttachment";
import { VideoAttachment } from "@/components/features/VideoAttachment";
import { isUserAuthoredMessage } from "@/types/chat";
import type {
  UIMessage,
  ChatThread,
  ChatMessage,
  ChatMessageAttachment,
} from "@/types/chat";

const LEAD_AGENT_ID = "system";

const markdownProseClass =
  "prose prose-sm dark:prose-invert max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0";

function isThreadOlderThanThreeDays(thread: ChatThread): boolean {
  const updatedAt = new Date(thread.updated_at);
  const threeDaysAgo = new Date();
  threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
  return updatedAt < threeDaysAgo;
}

function apiMessageToUIMessage(msg: ChatMessage): UIMessage {
  const isSystem = msg.author_type === "system";
  const isUserMessage = !isSystem && isUserAuthoredMessage(msg.author_type);
  return {
    id: msg.id,
    role: isSystem ? "system" : isUserMessage ? "user" : "agent",
    authorType: msg.author_type,
    content: msg.message,
    thinking: msg.thinking,
    errorType: msg.error_type,
    timestamp: new Date(msg.created_at),
    skillCalls: msg.skill_calls,
    attachments: msg.attachments,
  };
}

function hasUIAttachments(msg: UIMessage): boolean {
  return (
    !!msg.attachments &&
    msg.attachments.some(
      (a) => a.type === "card" || a.type === "choice" || a.type === "image" || a.type === "video",
    )
  );
}

const optionLabels: Record<string, string> = { a: "A.", b: "B.", c: "C." };

function CardAttachment({ att }: { att: ChatMessageAttachment }) {
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

function ChoiceAttachment({
  att,
  onSendMessage,
}: {
  att: ChatMessageAttachment;
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

function buildLeadThreadPath(threadId?: string | null) {
  if (!threadId) return "/lead";
  const params = new URLSearchParams({ thread: threadId });
  return `/lead?${params.toString()}`;
}

export default function LeadChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Thread state
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [isNewThread, setIsNewThread] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Message state
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const wasCancelledRef = useRef(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Fetch thread list
  const {
    data: threads = [],
    isLoading: isLoadingThreads,
    refetch: refetchThreads,
  } = useQuery({
    queryKey: ["leadChats"],
    queryFn: () => leadApi.listChats(),
  });

  // Initialize: select the most recent thread or start new
  useEffect(() => {
    if (isSending) return;

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
      setIsNewThread(true);
      setCurrentThreadId(null);
    } else {
      const sorted = [...threads].sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      );
      const mostRecent = sorted[0];

      if (isThreadOlderThanThreeDays(mostRecent)) {
        setIsNewThread(true);
        setCurrentThreadId(null);
      } else {
        setCurrentThreadId(mostRecent.id);
        setIsNewThread(false);
        router.replace(buildLeadThreadPath(mostRecent.id));
      }
    }
    setHasInitialized(true);
  }, [
    threads,
    isLoadingThreads,
    hasInitialized,
    searchParams,
    currentThreadId,
    isNewThread,
    router,
    isSending,
  ]);

  // Load messages when thread changes
  useEffect(() => {
    if (isSending) return;
    if (wasCancelledRef.current) {
      wasCancelledRef.current = false;
      return;
    }

    if (!currentThreadId || isNewThread) {
      setMessages([]);
      return;
    }

    const loadMessages = async () => {
      try {
        const response = await leadApi.listMessages(currentThreadId);
        const uiMessages = response.data.reverse().map(apiMessageToUIMessage);
        setMessages(uiMessages);
      } catch (err) {
        console.error("Failed to load messages:", err);
        setError("Failed to load message history");
      }
    };

    loadMessages();
  }, [currentThreadId, isNewThread, isSending]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Thread actions
  const handleSelectThread = useCallback(
    (threadId: string) => {
      setError(null);
      router.push(buildLeadThreadPath(threadId));
    },
    [router],
  );

  const handleNewThread = useCallback(() => {
    router.push("/lead?new=true");
  }, [router]);

  const handleUpdateTitle = useCallback(
    async (threadId: string, title: string) => {
      await leadApi.updateChatSummary(threadId, title);
      await refetchThreads();
    },
    [refetchThreads],
  );

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      await leadApi.deleteChat(threadId);
      await refetchThreads();

      if (currentThreadId === threadId) {
        const remaining = threads.filter((t) => t.id !== threadId);
        if (remaining.length > 0) {
          const sorted = [...remaining].sort(
            (a, b) =>
              new Date(b.updated_at).getTime() -
              new Date(a.updated_at).getTime(),
          );
          router.replace(buildLeadThreadPath(sorted[0].id));
        } else {
          setMessages([]);
          router.replace("/lead?new=true");
        }
      }
    },
    [refetchThreads, currentThreadId, threads, router],
  );

  // Send message with streaming
  const handleSendMessage = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!inputValue.trim() || isSending) return;

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

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        let threadId = currentThreadId;

        if (isNewThread || !threadId) {
          const newThread = await leadApi.createChat(
            undefined,
            userMessage.content,
          );
          threadId = newThread.id;
          setCurrentThreadId(threadId);
          setIsNewThread(false);
          await refetchThreads();
          router.replace(buildLeadThreadPath(threadId));
        }

        for await (const msg of leadApi.sendMessageStream(
          threadId,
          userMessage.content,
          abortController.signal,
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

        await refetchThreads();
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          wasCancelledRef.current = true;
          setMessages((prev) => [
            ...prev,
            {
              id: `system-${Date.now()}`,
              role: "system",
              content: "User cancelled the conversation",
              timestamp: new Date(),
            },
          ]);
        } else {
          const errorMessage =
            err instanceof Error ? err.message : "Failed to send message";
          setError(errorMessage);
          setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
        }
      } finally {
        abortControllerRef.current = null;
        setIsSending(false);
      }
    },
    [
      inputValue,
      isSending,
      currentThreadId,
      isNewThread,
      refetchThreads,
      router,
    ],
  );

  const handleStopGeneration = useCallback(async () => {
    abortControllerRef.current?.abort();
    if (currentThreadId) {
      try {
        await leadApi.cancelGeneration(currentThreadId);
      } catch {
        // Best-effort cancellation
      }
    }
  }, [currentThreadId]);

  const sendTextMessage = useCallback((text: string) => {
    setInputValue(text);
    setTimeout(() => {
      const form = document.querySelector("form") as HTMLFormElement | null;
      form?.requestSubmit();
    }, 0);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar */}
      <ChatSidebar
        agentId={LEAD_AGENT_ID}
        activeTab="chat"
        threads={threads}
        currentThreadId={currentThreadId}
        isNewThread={isNewThread}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onUpdateTitle={handleUpdateTitle}
        onDeleteThread={handleDeleteThread}
        isLoading={isLoadingThreads}
        hideNavLinks
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col p-6">
        {/* Header */}
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border bg-primary/10">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Team Lead</h1>
            <p className="text-sm text-muted-foreground">
              Team lead assistant
            </p>
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
                  Send a message to chat with the team lead
                </p>
              </div>
            ) : (
              messages.map((msg) =>
                msg.role === "system" ? (
                  <div key={msg.id} className="flex justify-center w-full">
                    <span
                      className={cn(
                        "text-xs px-3 py-1 rounded-full",
                        msg.errorType
                          ? "text-destructive bg-destructive/10"
                          : "text-muted-foreground bg-muted",
                      )}
                    >
                      {msg.content}
                    </span>
                  </div>
                ) : msg.authorType === "thinking" ? (
                  <div key={msg.id} className="flex w-full max-w-[85%] pl-10">
                    <ThinkingBlock thinking={msg.content} />
                  </div>
                ) : msg.authorType === "skill" ? (
                  <div key={msg.id} className="flex w-full max-w-[85%] pl-10">
                    <div className="space-y-2">
                      {msg.skillCalls && msg.skillCalls.length > 0 && (
                        <SkillCallBadgeList skillCalls={msg.skillCalls} />
                      )}
                      {hasUIAttachments(msg) &&
                        msg.attachments!
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
                              {att.type === "video" && (
                                <VideoAttachment att={att} />
                              )}
                            </div>
                          ))}
                    </div>
                  </div>
                ) : (
                  <React.Fragment key={msg.id}>
                    {msg.thinking && msg.role === "agent" && (
                      <div className="flex w-full max-w-[85%] pl-10">
                        <ThinkingBlock thinking={msg.thinking} />
                      </div>
                    )}
                    <div
                      className={cn(
                        "flex w-full gap-2 max-w-[85%]",
                        msg.role === "user" ? "ml-auto flex-row-reverse" : "",
                      )}
                    >
                      {msg.role === "agent" ? (
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-primary text-primary-foreground">
                          <Bot className="h-4 w-4" />
                        </div>
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
                                  {att.type === "video" && (
                                    <VideoAttachment att={att} />
                                  )}
                                </div>
                              ))}
                          </div>
                        )}
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
                  </React.Fragment>
                ),
              )
            )}
            {isSending && (
              <div className="flex w-full gap-2 max-w-[85%]">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-primary text-primary-foreground">
                  <Bot className="h-4 w-4" />
                </div>
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
              {isSending ? (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleStopGeneration}
                  title="Stop generation"
                >
                  <Square className="h-4 w-4" />
                  <span className="sr-only">Stop</span>
                </Button>
              ) : (
                <Button
                  type="submit"
                  disabled={!inputValue.trim()}
                  title="Send message"
                >
                  <Send className="h-4 w-4" />
                  <span className="sr-only">Send</span>
                </Button>
              )}
            </form>
          </div>
        </Card>
      </div>
    </div>
  );
}
