"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { Send, Bot, User, ArrowLeft, Settings, Activity } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

// Mock types
type Agent = {
  id: string;
  name: string;
  description: string;
  status: "active" | "inactive" | "running";
  model: string;
};

type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
};

// Mock fetch
const fetchAgent = async (id: string): Promise<Agent> => {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return {
    id,
    name: "Research Assistant",
    description:
      "Helps gather information from the web and summarize findings.",
    status: "active",
    model: "gpt-4-turbo",
  };
};

function AgentDetailContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const { data: agent, isLoading } = useQuery({
    queryKey: ["agent", id],
    queryFn: () => fetchAgent(id!),
    enabled: !!id,
  });

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "agent",
      content:
        "Hello! I am ready to help you with your research. What topic shall we explore today?",
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputValue.trim() || isSending) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setIsSending(true);

    // Simulate agent response
    setTimeout(() => {
      const agentMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "agent",
        content: `I received your message: "${userMsg.content}". This is a mock response from the agent backend.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, agentMsg]);
      setIsSending(false);
    }, 1500);
  };

  if (isLoading) {
    return (
      <div className="container py-10">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-1/3 bg-muted rounded" />
          <div className="h-[500px] bg-muted rounded" />
        </div>
      </div>
    );
  }

  if (!agent) return <div className="container py-10">Agent not found</div>;

  return (
    <div className="container flex h-[calc(100vh-3.5rem)] flex-col py-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              {agent.name}
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
                  agent.status === "active"
                    ? "bg-green-50 text-green-700 ring-green-600/20"
                    : "bg-gray-50 text-gray-600 ring-gray-500/10",
                )}
              >
                {agent.status}
              </span>
            </h1>
            <p className="text-sm text-muted-foreground">{agent.description}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <Activity className="mr-2 h-4 w-4" />
            Logs
          </Button>
          <Button variant="outline" size="sm">
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </Button>
        </div>
      </div>

      {/* Chat Interface */}
      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardHeader className="border-b py-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Bot className="h-4 w-4" />
            <span>Model: {agent.model}</span>
          </div>
        </CardHeader>

        <CardContent
          className="flex-1 overflow-y-auto p-4 space-y-4"
          ref={scrollRef}
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "flex w-full gap-2 max-w-[80%]",
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
                {msg.content}
              </div>
            </div>
          ))}
          {isSending && (
            <div className="flex w-full gap-2 max-w-[80%]">
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
              disabled={isSending}
              className="flex-1"
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

export default function AgentDetailPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <AgentDetailContent />
    </Suspense>
  );
}
