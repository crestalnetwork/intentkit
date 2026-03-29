"use client";

import { useQuery } from "@tanstack/react-query";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";

import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, Calendar, User, Tag, Copy, Check, MoreVertical, Download } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { postApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

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

  useEffect(() => {
    if (post && post.slug) {
        router.replace(`/agent/${post.agent_id}/post/${post.slug}`);
    }
  }, [post, router]);

  const [copied, setCopied] = useState(false);

  const handleCopyMarkdown = useCallback(async () => {
    if (!post?.markdown) return;
    const text = `# ${post.title}\n\n${post.markdown}`;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [post]);

  const handleDownloadPdf = useCallback(() => {
    if (!post?.id) return;
    window.open(postApi.getPdfUrl(post.id), "_blank");
  }, [post]);

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
    <div className="container py-10 max-w-[768px] mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <Button
            variant="ghost"
            className="pl-0 hover:pl-0 hover:bg-transparent text-muted-foreground hover:text-foreground"
            onClick={handleBack}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {fromAgentId ? "Back to Agent Posts" : "Back to Posts"}
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
                 <span className="font-medium text-foreground">{post.agent_name}</span>
                 <Link href={`/agent/${post.agent_id}`} className="text-xs underline hover:text-primary">
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
                        {post.tags.map((tag: string) => (
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
