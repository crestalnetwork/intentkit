"use client";

import { useParams } from "next/navigation";
import { Timeline } from "@/components/features/Timeline";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function AgentActivitiesPage() {
    const params = useParams();
    const agentId = params.id as string;

    return (
        <div className="container py-10 max-w-4xl">
            <div className="mb-8">
                <Button variant="ghost" className="pl-0 hover:pl-0 hover:bg-transparent text-muted-foreground hover:text-foreground" asChild>
                    <Link href={`/agent/${agentId}`}>
                        <ArrowLeft className="mr-2 h-4 w-4" />
                        Back to Agent
                    </Link>
                </Button>
                <div className="mt-4">
                    <h1 className="text-3xl font-bold tracking-tight">Agent Activities</h1>
                    <p className="text-muted-foreground mt-2">
                        Recent activities and events for this agent.
                    </p>
                </div>
            </div>
            <div className="rounded-xl border bg-card text-card-foreground shadow p-6">
                <Timeline agentId={agentId} />
            </div>
        </div>
    );
}
