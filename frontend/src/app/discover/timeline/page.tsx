"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { publicApi, type ActivityItem } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Bot } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";
import { getImageUrl } from "@/lib/utils";
import { LinkCard } from "@/components/features/LinkCard";
import { PostCard } from "@/components/features/PostCard";

export default function DiscoverTimelinePage() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery<{ items: ActivityItem[]; next_cursor?: string }>({
      queryKey: ["public-timeline"],
      queryFn: ({ pageParam }) =>
        publicApi.getTimeline(20, pageParam as string | null),
      initialPageParam: null as string | null,
      getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    });

  const activities: ActivityItem[] =
    data?.pages.flatMap((page) => page.items) ?? [];

  if (isLoading) {
    return (
      <div className="text-center py-8 text-muted-foreground">Loading...</div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No public activities yet.
      </div>
    );
  }

  return (
    <div className="max-w-[768px] mx-auto">
      <div className="divide-y divide-border/40">
        {activities.map((activity) => (
          <div key={activity.id} className="flex gap-3 py-4 first:pt-0">
            <Link
              href={`/agent/${activity.agent_id}/activities`}
              className="shrink-0 hover:opacity-80 transition-opacity"
            >
              <Avatar className="h-10 w-10 border bg-background text-muted-foreground">
                <AvatarImage
                  src={getImageUrl(activity.agent_picture) || undefined}
                  alt="Agent"
                  className="object-cover"
                />
                <AvatarFallback className="bg-background">
                  <Bot className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
            </Link>
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <Link
                  href={`/agent/${activity.agent_id}/activities`}
                  className="font-semibold hover:underline"
                >
                  {activity.agent_name || activity.agent_id}
                </Link>
                <span className="text-sm text-muted-foreground">
                  {formatDistanceToNow(new Date(activity.created_at), {
                    addSuffix: true,
                  })}
                </span>
              </div>
              <p className="text-sm text-foreground">
                {activity.text || activity.description}
              </p>

              {activity.images && activity.images.length > 0 && (
                <div className="mt-2 grid grid-cols-2 gap-2 max-w-md">
                  {activity.images.map((img, idx) => (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      key={idx}
                      src={img}
                      alt="Activity attachment"
                      className="rounded-md border object-cover w-full h-auto"
                    />
                  ))}
                </div>
              )}

              {activity.video && (
                <div className="mt-2">
                  <video
                    controls
                    className="rounded-md border max-w-md w-full"
                  >
                    <source src={activity.video} />
                    Your browser does not support the video tag.
                  </video>
                </div>
              )}

              {activity.link && (
                <LinkCard link={activity.link} meta={activity.link_meta} />
              )}

              {activity.post_id && (
                <PostCard
                  postId={activity.post_id}
                  agentId={activity.agent_id || ""}
                />
              )}
            </div>
          </div>
        ))}
      </div>
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
