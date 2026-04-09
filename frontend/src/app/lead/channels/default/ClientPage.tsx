"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useQuery, useInfiniteQuery } from "@tanstack/react-query";
import { Bot, User, MessageSquareText, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { leadApi, channelApi } from "@/lib/api";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { SkillCallBadgeList } from "@/components/features/SkillCallBadge";
import { ThinkingBlock } from "@/components/features/ThinkingBlock";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { ImageAttachment } from "@/components/features/ImageAttachment";
import { VideoAttachment } from "@/components/features/VideoAttachment";
import { isUserAuthoredMessage } from "@/types/chat";
import type {
  UIMessage,
  ChatMessage,
  ChatMessageAttachment,
} from "@/types/chat";
import { LEAD_AGENT_ID, buildExtraNavLinks, CHANNEL_DISPLAY_NAMES } from "../../constants";

const markdownProseClass =
  "prose prose-sm dark:prose-invert max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0";

function apiMessageToUIMessage(msg: ChatMessage): UIMessage {
  return {
    id: msg.id,
    role: msg.author_type === "agent" ? "agent"
      : msg.author_type === "system" ? "system"
      : msg.author_type === "thinking" ? "agent"
      : msg.author_type === "skill" ? "agent"
      : isUserAuthoredMessage(msg.author_type) ? "user"
      : "user",
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
      (a) => a.type === "card" || a.type === "image" || a.type === "video",
    )
  );
}

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
    return (
      <a href={att.url!} target="_blank" rel="noopener noreferrer">
        {card}
      </a>
    );
  }
  return card;
}

function buildLeadThreadPath(threadId?: string | null) {
  if (!threadId) return "/lead";
  const params = new URLSearchParams({ thread: threadId });
  return `/lead?${params.toString()}`;
}

export default function DefaultChannelPage() {
  const router = useRouter();
  const scrollRef = useRef<HTMLDivElement>(null);
  const topSentinelRef = useRef<HTMLDivElement>(null);
  const [autoScrolled, setAutoScrolled] = useState(false);

  // Sidebar data
  const {
    data: threads = [],
    isLoading: isLoadingThreads,
    refetch: refetchThreads,
  } = useQuery({
    queryKey: ["leadChats"],
    queryFn: () => leadApi.listChats(),
  });

  const { data: defaultChannelInfo } = useQuery({
    queryKey: ["defaultChannelInfo"],
    queryFn: () => channelApi.getDefaultChannel(),
    staleTime: 5 * 60 * 1000,
  });

  const extraNavLinks = useMemo(
    () => buildExtraNavLinks(defaultChannelInfo),
    [defaultChannelInfo],
  );

  // Fetch messages with infinite scroll (newest first from API, reversed for display)
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isLoadingMessages,
  } = useInfiniteQuery({
    queryKey: ["defaultChannelMessages"],
    queryFn: ({ pageParam }) =>
      channelApi.listDefaultChannelMessages(pageParam as string | undefined, 50),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_cursor : undefined,
  });

  // Flatten and reverse pages to get chronological order
  const messages = useMemo(() => {
    if (!data) return [];
    const allMessages: UIMessage[] = [];
    // Pages come newest-first; reverse to get oldest-first for display
    for (let i = data.pages.length - 1; i >= 0; i--) {
      const page = data.pages[i];
      const reversed = [...page.data].reverse();
      allMessages.push(...reversed.map(apiMessageToUIMessage));
    }
    return allMessages;
  }, [data]);

  // Auto-scroll to bottom on initial load
  useEffect(() => {
    if (!autoScrolled && messages.length > 0 && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      setAutoScrolled(true);
    }
  }, [messages, autoScrolled]);

  // Load more when scrolling to top
  useEffect(() => {
    const sentinel = topSentinelRef.current;
    const container = scrollRef.current;
    if (!sentinel || !container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          const prevScrollHeight = container.scrollHeight;
          fetchNextPage().then(() => {
            // Maintain scroll position after prepending older messages
            requestAnimationFrame(() => {
              const newScrollHeight = container.scrollHeight;
              container.scrollTop = newScrollHeight - prevScrollHeight;
            });
          });
        }
      },
      { root: container, threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Sidebar handlers
  const handleSelectThread = useCallback(
    (threadId: string) => {
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
    },
    [refetchThreads],
  );

  const channelLabel = defaultChannelInfo?.default_channel
    ? CHANNEL_DISPLAY_NAMES[defaultChannelInfo.default_channel] ??
      defaultChannelInfo.default_channel
    : "Default Channel";

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar */}
      <ChatSidebar
        agentId={LEAD_AGENT_ID}
        activeTab="chat"
        threads={threads}
        currentThreadId={null}
        isNewThread={false}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onUpdateTitle={handleUpdateTitle}
        onDeleteThread={handleDeleteThread}
        isLoading={isLoadingThreads}
        hideNavLinks
        extraNavLinks={extraNavLinks}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col p-6">
        {/* Header */}
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border bg-primary/10">
            <MessageSquareText className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Default Channel</h1>
            <p className="text-sm text-muted-foreground">
              {channelLabel} conversation history (read-only)
            </p>
          </div>
        </div>

        {/* Chat Interface - Read Only */}
        <Card className="flex-1 flex flex-col overflow-hidden">
          <CardHeader className="border-b py-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <MessageSquareText className="h-4 w-4" />
              <span>Default Channel Messages</span>
              <span className="text-xs">
                ({messages.length} message{messages.length !== 1 ? "s" : ""})
              </span>
            </div>
          </CardHeader>

          <CardContent
            className="flex-1 overflow-y-auto p-4 space-y-4"
            ref={scrollRef}
          >
            {/* Top sentinel for infinite scroll */}
            <div ref={topSentinelRef} className="h-1" />

            {isFetchingNextPage && (
              <div className="flex justify-center py-2">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            )}

            {isLoadingMessages ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin mb-4" />
                <p className="text-sm">Loading messages...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                <MessageSquareText className="h-12 w-12 mb-4 opacity-50" />
                <p className="text-lg font-medium">No messages yet</p>
                <p className="text-sm">
                  Messages from the default channel will appear here
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
                              a.type === "image" ||
                              a.type === "video",
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
                                  a.type === "image" ||
                                  a.type === "video",
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
          </CardContent>

          {/* Read-only notice instead of input */}
          <div className="p-3 border-t bg-muted/30 text-center">
            <p className="text-xs text-muted-foreground">
              This is a read-only view of the default channel conversation
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
