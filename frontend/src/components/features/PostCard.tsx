"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { postApi } from "@/lib/api";

interface PostCardProps {
  postId: string;
  agentId: string;
}

export function PostCard({ postId, agentId }: PostCardProps) {
  const { data: post } = useQuery({
    queryKey: ["post", postId],
    queryFn: () => postApi.getById(postId),
  });

  if (!post) {
    return null;
  }

  const href = post.slug
    ? `/agent/${post.agent_id}/post/${post.slug}`
    : `/post/${post.id}`;

  return (
    <Link
      href={href}
      className="mt-2 flex h-[4.5rem] max-w-sm overflow-hidden rounded-md border transition-colors hover:bg-accent/50"
    >
      <div className="flex h-full w-[4.5rem] shrink-0 items-center justify-center bg-muted/50">
        <FileText className="h-6 w-6 text-muted-foreground" />
      </div>
      <div className="flex min-w-0 flex-col justify-center px-3 py-1.5">
        <p className="truncate text-sm font-medium leading-snug">
          {post.title}
        </p>
        <p className="line-clamp-2 text-xs leading-tight text-muted-foreground">
          {post.excerpt || "No excerpt available."}
        </p>
      </div>
    </Link>
  );
}
