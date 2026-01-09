"use client";

import { Timeline } from "@/components/features/Timeline";

export default function TimelinePage() {
    return (
        <div className="container py-10">
            <div className="mb-8">
                <h1 className="text-3xl font-bold tracking-tight">Timeline</h1>
                <p className="text-muted-foreground mt-2">
                    View recent agent activities and system events.
                </p>
            </div>
            <div className="rounded-xl border bg-card text-card-foreground shadow p-6">
                <Timeline />
            </div>
        </div>
    );
}
