"use client";

import { useState, useRef, useEffect, Suspense, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Send,
  Bot,
  User,
  ArrowLeft,
  RefreshCw,
  Info,
  AlertCircle,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { agentApi, chatApi, generateChatId, generateUserId } from "@/lib/api";
import type { UIMessage } from "@/types/chat";

function AgentChatContent() {
  const searchParams = useSearchParams();
  const agentId = searchParams.get("id");

  const {
    data: agent,
    isLoading: isLoadingAgent,
    error: agentError,
  } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId!),
    enabled: !!agentId,
  });

  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [chatId] = useState(() => generateChatId());
  const [userId] = useState(() => generateUserId());
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

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
        const response = await chatApi.sendMessage(agentId, {
          chat_id: chatId,
          user_id: userId,
          message: inputValue,
        });

        // Process response messages
        const agentMessages: UIMessage[] = response
          .filter((msg) => msg.author_id !== userId)
          .map((msg) => ({
            id: msg.id,
            role: "agent" as const,
            content: msg.message,
            timestamp: new Date(msg.created_at),
            skillCalls: msg.skill_calls,
          }));

        if (agentMessages.length > 0) {
          setMessages((prev) => [...prev, ...agentMessages]);
        } else {
          // If no agent messages, show a placeholder
          setMessages((prev) => [
            ...prev,
            {
              id: `agent-${Date.now()}`,
              role: "agent",
              content: "Agent processed your message but returned no response.",
              timestamp: new Date(),
            },
          ]);
        }
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
    [inputValue, isSending, agentId, chatId, userId],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
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

  return (
    <div className="container flex h-[calc(100vh-3.5rem)] flex-col py-6">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="flex items-center gap-3">
            {agent.picture ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={agent.picture}
                alt={displayName}
                className="h-10 w-10 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-5 w-5 text-primary" />
              </div>
            )}
            <div>
              <h1 className="text-xl font-bold">{displayName}</h1>
              <p className="text-sm text-muted-foreground line-clamp-1">
                {agent.purpose || "No description"}
              </p>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={clearChat}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Clear Chat
          </Button>
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
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Chat ID:</span>
            <span className="font-mono text-xs bg-background px-2 py-0.5 rounded">
              {chatId}
            </span>
          </div>
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
            <span>Chat Session</span>
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
                <div
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                    msg.role === "agent"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted",
                  )}
                >
                  {msg.role === "agent" ? (
                    <Bot className="h-4 w-4" />
                  ) : (
                    <User className="h-4 w-4" />
                  )}
                </div>
                <div
                  className={cn(
                    "rounded-lg px-4 py-2 text-sm",
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground",
                  )}
                >
                  <div className="whitespace-pre-wrap break-words">
                    {msg.content}
                  </div>
                  {msg.skillCalls && msg.skillCalls.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/50 text-xs opacity-70">
                      <span className="font-medium">Skills used:</span>{" "}
                      {msg.skillCalls.map((sc) => sc.name).join(", ")}
                    </div>
                  )}
                </div>
              </div>
            ))
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
              placeholder="Type a message..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isSending}
              className="flex-1"
              autoFocus
            />
            <Button type="submit" disabled={isSending || !inputValue.trim()}>
              <Send className="h-4 w-4" />
              <span className="sr-only">Send</span>
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}

export default function AgentChatPage() {
  return (
    <Suspense
      fallback={
        <div className="container py-10">
          <div className="animate-pulse space-y-4">
            <div className="h-8 w-1/3 bg-muted rounded" />
            <div className="h-[500px] bg-muted rounded" />
          </div>
        </div>
      }
    >
      <AgentChatContent />
    </Suspense>
  );
}
