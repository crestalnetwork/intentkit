"use client";

import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Activity, Bell, FileText, MessageSquare, StickyNote, Wallet, Bot } from "lucide-react";
import { activityApi } from "@/lib/api";
import {
    Card,
    CardHeader,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function getActivityIcon(type: string) {
    switch (type) {
        case "post":
            return <FileText className="h-4 w-4" />;
        case "chat":
            return <MessageSquare className="h-4 w-4" />;
        case "wallet":
            return <Wallet className="h-4 w-4" />;
        case "note":
            return <StickyNote className="h-4 w-4" />;
        default:
            return <Activity className="h-4 w-4" />;
    }
}

// ... imports remain the same

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
        <div className="space-y-6">
            {/* Refresh button removed */}
            <div className="relative border-l border-muted pl-6 ml-4 space-y-8">
                {activities.map((activity) => (
                    <div key={activity.id} className="relative">
                        <span className="absolute -left-10 top-0 flex h-8 w-8 items-center justify-center rounded-full border bg-background text-muted-foreground overflow-hidden">
                            {agentId ? (
                                agentPicture ? (
                                    /* eslint-disable-next-line @next/next/no-img-element */
                                    <img 
                                        src={agentPicture} 
                                        alt="Agent" 
                                        className="h-full w-full object-cover"
                                    />
                                ) : (
                                    <Bot className="h-4 w-4" />
                                )
                            ) : (
                                getActivityIcon(activity.activity_type || "default")
                            )}
                        </span>
                        <div className="space-y-1">
                            <div className="flex items-center gap-2">
                                <span className="font-semibold">{activity.agent_name || activity.agent_id}</span>
                                <span className="text-sm text-muted-foreground">
                                    {formatDistanceToNow(new Date(activity.created_at), { addSuffix: true })}
                                </span>
                            </div>
                            <p className="text-sm text-foreground">{activity.text || activity.description}</p>
                            
                            {/* Images */}
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

                             {/* Video */}
                            {activity.video && (
                                <div className="mt-2">
                                    <video controls className="rounded-md border max-w-md w-full">
                                        <source src={activity.video} />
                                        Your browser does not support the video tag.
                                    </video>
                                </div>
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
        </div>
    );
}
