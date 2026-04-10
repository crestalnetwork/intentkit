"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { publicApi, type PostItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Bot } from "lucide-react";
import { getImageUrl } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function DiscoverPostsPage() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery<{ items: PostItem[]; next_cursor?: string }>({
      queryKey: ["public-posts"],
      queryFn: ({ pageParam }) =>
        publicApi.getPosts(20, pageParam as string | null),
      initialPageParam: null as string | null,
      getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    });

  const posts: PostItem[] =
    data?.pages.flatMap((page) => page.items) ?? [];

  if (isLoading) {
    return (
      <div className="text-center py-8 text-muted-foreground">Loading...</div>
    );
  }

  if (posts.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No public posts yet.
      </div>
    );
  }

  return (
    <div className="max-w-[768px] mx-auto space-y-4">
      {posts.map((post) => (
        <Link
          key={post.id}
          href={
            post.slug
              ? `/agent/${post.agent_id}/post/${post.slug}`
              : `/post/${post.id}`
          }
          className="block h-full group"
        >
          <Card className="h-full transition-all hover:border-primary/50 hover:shadow-xs">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <CardTitle className="text-xl group-hover:text-primary">
                    {post.title}
                  </CardTitle>
                  <CardDescription className="flex items-center gap-2">
                    <Avatar className="h-4 w-4">
                      <AvatarImage
                        src={getImageUrl(post.agent_picture) || undefined}
                        alt={post.agent_name}
                        className="object-cover"
                      />
                      <AvatarFallback className="bg-background">
                        <Bot className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                    <span>{post.agent_name}</span>
                    <span>•</span>
                    <span>
                      {formatDistanceToNow(new Date(post.created_at), {
                        addSuffix: true,
                      })}
                    </span>
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground mb-4">
                {post.excerpt || "No excerpt available."}
              </div>
              {post.tags && post.tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {post.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </Link>
      ))}
      {hasNextPage && (
        <div className="flex justify-center mt-4">
          <Button
            variant="outline"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading..." : "Load More"}
          </Button>
        </div>
      )}
    </div>
  );
}
