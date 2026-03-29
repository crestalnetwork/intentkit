"use client";

import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Bell, Bot } from "lucide-react";
import { activityApi } from "@/lib/api";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import Link from "next/link";
import { getImageUrl } from "@/lib/utils";
import { LinkCard } from "@/components/features/LinkCard";
import { PostCard } from "@/components/features/PostCard";

interface TimelineProps {
    agentId?: string;
    agentPicture?: string | null;
}

export function Timeline({ agentId, agentPicture }: TimelineProps) {
    const {
        data: activities,
        isLoading,
        error,
        refetch,
    } = useQuery({
        queryKey: agentId ? ["activities", agentId] : ["activities"],
        queryFn: () => agentId ? activityApi.getByAgent(agentId, 50) : activityApi.getAll(50),
    });

    if (isLoading) {
        return (
            <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                    <Card key={i} className="animate-pulse">
                        <CardHeader className="h-20 bg-muted/50" />
                    </Card>
                ))}
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center text-destructive">
                <p className="font-medium">Error loading timeline</p>
                <Button variant="link" onClick={() => refetch()} className="mt-2">
                    Try Again
                </Button>
            </div>
        );
    }

    if (!activities?.length) {
        return (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                <Bell className="mb-4 h-12 w-12 opacity-20" />
                <h3 className="text-lg font-semibold">No activities yet</h3>
                <p className="text-sm">Activities from your agents will appear here.</p>
            </div>
        );
    }

    return (
        <div className="divide-y divide-border/40">
            {activities.map((activity) => (
                <div key={activity.id} className="flex gap-3 py-4 first:pt-0">
                    <Link href={`/agent/${activity.agent_id || agentId}/activities`} className="shrink-0 hover:opacity-80 transition-opacity">
                        <Avatar className="h-10 w-10 border bg-background text-muted-foreground">
                            <AvatarImage src={getImageUrl(agentId ? agentPicture : activity.agent_picture) || undefined} alt="Agent" className="object-cover" />
                            <AvatarFallback className="bg-background">
                                <Bot className="h-4 w-4" />
                            </AvatarFallback>
                        </Avatar>
                    </Link>
                    <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                            <Link href={`/agent/${activity.agent_id || agentId}/activities`} className="font-semibold hover:underline">
                                {activity.agent_name || activity.agent_id}
                            </Link>
                            <span className="text-sm text-muted-foreground">
                                {formatDistanceToNow(new Date(activity.created_at), { addSuffix: true })}
                            </span>
                        </div>
                        <p className="text-sm text-foreground">{activity.text || activity.description}</p>

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
                                <video controls className="rounded-md border max-w-md w-full">
                                    <source src={activity.video} />
                                    Your browser does not support the video tag.
                                </video>
                            </div>
                        )}

                        {activity.link && (
                            <LinkCard link={activity.link} meta={activity.link_meta} />
                        )}

                        {activity.post_id && (
                            <PostCard postId={activity.post_id} agentId={activity.agent_id || agentId || ""} />
                        )}

                        {activity.details && Object.keys(activity.details).length > 0 && (
                            <div className="rounded-md bg-muted/50 p-3 mt-2 text-xs font-mono">
                                <pre className="whitespace-pre-wrap">
                                    {JSON.stringify(activity.details, null, 2)}
                                </pre>
                            </div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
