"use client";

import { useQuery } from "@tanstack/react-query";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
// import ReactMarkdown from "react-markdown";

import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, Calendar, User, Tag, Copy, Check, MoreVertical, Download } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { postApi, agentApi } from "@/lib/api";
import { useAgentSlugRewrite } from "@/hooks/useAgentSlugRewrite";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function AgentPostPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;
  const slug = params.slug as string;

  const { data: agent } = useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => agentApi.getById(agentId),
    enabled: !!agentId,
  });

  useAgentSlugRewrite(agentId, agent?.slug);

  // The real agent ID for API calls (agentId from params may be a slug after URL rewrite)
  const resolvedId = agent?.id;

  const {
    data: post,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["post", resolvedId, slug],
    queryFn: () => postApi.getBySlug(resolvedId!, slug),
    enabled: !!resolvedId && !!slug,
  });

  const [copied, setCopied] = useState(false);

  const handleCopyMarkdown = useCallback(async () => {
    if (!post?.markdown) return;
    const text = `# ${post.title}\n\n${post.markdown}`;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [post]);

  const handleDownloadPdf = useCallback(() => {
    if (!resolvedId || !slug) return;
    window.open(postApi.getPdfUrlBySlug(resolvedId, slug), "_blank");
  }, [resolvedId, slug]);

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
    <div className="container py-10 max-w-[768px] mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <Button
            variant="ghost"
            className="pl-0 hover:pl-0 hover:bg-transparent text-muted-foreground hover:text-foreground"
            onClick={handleBack}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Agent Posts
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={handleCopyMarkdown}>
              {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
              {copied ? "Copied!" : "Copy as Markdown"}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleDownloadPdf}>
              <Download className="mr-2 h-4 w-4" />
              Download PDF
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
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

        <div>
          <div className="prose prose-stone dark:prose-invert max-w-none">
            <MarkdownRenderer>{post.markdown || ""}</MarkdownRenderer>
          </div>
        </div>
      </article>
    </div>
  );
}
