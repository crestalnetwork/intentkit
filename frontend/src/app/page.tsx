"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus, Bot } from "lucide-react";

// Mock type for Agent
type Agent = {
  id: string;
  name: string;
  description: string;
  status: "active" | "inactive" | "running";
  updated_at: string;
};

// Mock fetch function - replace with actual API call later
const fetchAgents = async (): Promise<Agent[]> => {
  // In a real app, this would be:
  // const res = await fetch('/api/agents')
  // if (!res.ok) throw new Error('Network response was not ok')
  // return res.json()

  // Simulating API delay
  await new Promise((resolve) => setTimeout(resolve, 1000));

  return [
    {
      id: "1",
      name: "Research Assistant",
      description:
        "Helps gather information from the web and summarize findings.",
      status: "active",
      updated_at: "2024-01-20T10:00:00Z",
    },
    {
      id: "2",
      name: "Coding Companion",
      description: "Assists with writing, debugging, and refactoring code.",
      status: "running",
      updated_at: "2024-01-21T14:30:00Z",
    },
    {
      id: "3",
      name: "Social Media Manager",
      description: "Drafts and schedules posts for Twitter and LinkedIn.",
      status: "inactive",
      updated_at: "2024-01-19T09:15:00Z",
    },
  ];
};

export default function Dashboard() {
  const {
    data: agents,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  return (
    <div className="container py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agents</h1>
          <p className="text-muted-foreground mt-2">
            Manage and monitor your autonomous agents.
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Create Agent
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="h-[140px] bg-muted/50" />
            </Card>
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          Error loading agents. Please try again later.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents?.map((agent) => (
            <Card key={agent.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xl">{agent.name}</CardTitle>
                  <Bot className="h-5 w-5 text-muted-foreground" />
                </div>
                <CardDescription className="line-clamp-2 min-h-[2.5rem]">
                  {agent.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1">
                <div className="flex items-center text-sm text-muted-foreground">
                  <span
                    className={`mr-2 inline-block h-2 w-2 rounded-full ${
                      agent.status === "active"
                        ? "bg-green-500"
                        : agent.status === "running"
                          ? "bg-blue-500"
                          : "bg-gray-300"
                    }`}
                  />
                  <span className="capitalize">{agent.status}</span>
                </div>
              </CardContent>
              <CardFooter>
                <Button asChild className="w-full" variant="secondary">
                  <Link href={`/agent?id=${agent.id}`}>View Details</Link>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
