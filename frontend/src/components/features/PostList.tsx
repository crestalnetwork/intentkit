
"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { postApi } from "@/lib/api";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, Eye } from "lucide-react";

export function PostList() {
    const {
        data: posts,
        isLoading,
        error,
        refetch,
        isRefetching,
    } = useQuery({
        queryKey: ["posts"],
        queryFn: () => postApi.getAll(50),
    });

    if (isLoading) {
        return (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {[1, 2, 3].map((i) => (
                    <Card key={i} className="animate-pulse">
                        <CardHeader className="h-[140px] bg-muted/50" />
                    </Card>
                ))}
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-center text-destructive">
                <p className="font-medium">Error loading posts</p>
                <Button variant="link" onClick={() => refetch()}>
                    Try Again
                </Button>
            </div>
        );
    }

    if (!posts?.length) {
        return (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                <FileText className="mb-4 h-12 w-12 opacity-20" />
                <h3 className="text-lg font-semibold">No posts yet</h3>
                <p className="text-sm">Posts from your agents will appear here.</p>
                <Button variant="outline" onClick={() => refetch()} className="mt-4">
                    Refresh
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex justify-end">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => refetch()}
                    disabled={isRefetching}
                >
                    {isRefetching ? "Refreshing..." : "Refresh Posts"}
                </Button>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {posts.map((post) => (
                    <Link key={post.id} href={`/posts/view?id=${post.id}`} className="block h-full group">
                        <Card className="h-full transition-all hover:border-primary/50 hover:shadow-sm">
                            <CardHeader>
                                <div className="flex items-start justify-between">
                                    <div className="space-y-1">
                                        <CardTitle className="line-clamp-2 text-lg group-hover:text-primary">
                                            {post.title}
                                        </CardTitle>
                                        <CardDescription className="flex items-center gap-2">
                                            <span>{post.agent_name}</span>
                                            <span>•</span>
                                            <span>{formatDistanceToNow(new Date(post.created_at), { addSuffix: true })}</span>
                                        </CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className="line-clamp-3 text-sm text-muted-foreground mb-4">
                                    {post.summary || "No summary available."}
                                </div>
                                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                    <div className="flex items-center gap-1">
                                        <Eye className="h-3 w-3" />
                                        <span>{post.view_count} views</span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </Link>
                ))}
            </div>
        </div>
    );
}
