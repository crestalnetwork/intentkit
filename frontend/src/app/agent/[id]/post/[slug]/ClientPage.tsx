"use client";

import { useQuery } from "@tanstack/react-query";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
// import ReactMarkdown from "react-markdown";

import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, Calendar, User, Tag } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { postApi, agentApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function AgentPostPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;
  const slug = params.slug as string;

  const {
    data: post,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["post", agentId, slug],
    queryFn: () => postApi.getBySlug(agentId, slug),
    enabled: !!agentId && !!slug,
  });

  const { data: agent } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId),
    enabled: !!agentId,
  });

  const handleBack = () => {
    router.push(`/agent/${agentId}/posts`);
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

  if (error || !post) {
    return (
      <div className="container py-10 text-center">
        <h1 className="text-2xl font-bold text-destructive mb-4">
          {error ? "Error loading post" : "Post not found"}
        </h1>
        <Button variant="outline" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Agent Posts
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
          Back to Agent Posts
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
                 <Link href={`/agent/${agentId}`} className="text-xs underline hover:text-primary">
                    (View Agent)
                 </Link>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              <span>{formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}</span>
            </div>
            
            {post.tags && post.tags.length > 0 && (
                <div className="flex items-center gap-2">
                    <Tag className="h-4 w-4" />
                    <div className="flex gap-2">
                        {post.tags.map(tag => (
                            <Badge key={tag} variant="secondary" className="text-xs font-normal">
                                {tag}
                            </Badge>
                        ))}
                    </div>
                </div>
            )}
          </div>
        </header>

        <div className="prose prose-stone dark:prose-invert max-w-none">
          <MarkdownRenderer>{post.markdown || ""}</MarkdownRenderer>
        </div>
      </article>
    </div>
  );
}
