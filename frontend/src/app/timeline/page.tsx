"use client";

import { Timeline } from "@/components/features/Timeline";

export default function TimelinePage() {
    return (
        <div className="container py-10">
            <div className="max-w-[768px] mx-auto">
                <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight">Timeline</h1>
                    <p className="text-muted-foreground mt-2">
                        View recent agent activities and system events.
                    </p>
                </div>
                <Timeline />
            </div>
        </div>
    );
}
