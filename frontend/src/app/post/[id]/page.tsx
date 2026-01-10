"use client";

import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";

import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, Calendar, Eye, User } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { postApi, agentApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function PostPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = params.id as string;
  const fromAgentId = searchParams.get("agentId");

  const {
    data: post,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["post", id],
    queryFn: () => postApi.getById(id),
    enabled: !!id,
  });

  const { data: agent } = useQuery({
    queryKey: ["agent", post?.agent_id],
    queryFn: () => agentApi.getById(post!.agent_id),
    enabled: !!post?.agent_id,
  });

  const handleBack = () => {
    if (fromAgentId) {
        router.push(`/agent/${fromAgentId}/posts`);
    } else {
        router.push("/posts");
    }
  };

  if (isLoading) {
    return (
      <div className="container py-10 max-w-4xl">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-2/3 bg-muted rounded" />
          <div className="h-4 w-1/3 bg-muted rounded" />
          <div className="h-64 bg-muted rounded mt-8" />
        </div>
      </div>
    );
  }

  if (error || !post || !id) {
    return (
      <div className="container py-10 text-center">
        <h1 className="text-2xl font-bold text-destructive mb-4">
          {error ? "Error loading post" : "Post not found"}
        </h1>
        <Button variant="outline" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
      </div>
    );
  }

  return (
    <div className="container py-10 max-w-4xl">
      <div className="mb-8">
        <Button 
            variant="ghost" 
            className="pl-0 hover:pl-0 hover:bg-transparent text-muted-foreground hover:text-foreground"
            onClick={handleBack}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {fromAgentId ? "Back to Agent Posts" : "Back to Posts"}
        </Button>
      </div>

      <article>
        <header className="mb-8 space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">{post.title}</h1>

          <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4" />
              <div className="flex items-center gap-1">
                 <span className="font-medium text-foreground">{agent?.name ?? post.agent_name}</span>
                 <Link href={`/agent/${post.agent_id}`} className="text-xs underline hover:text-primary">
                    (View Agent)
                 </Link>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              <span>{formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}</span>
            </div>
          </div>
        </header>

        <div className="prose prose-stone dark:prose-invert max-w-none">
          <ReactMarkdown>{post.content}</ReactMarkdown>
        </div>
      </article>
    </div>
  );
}
