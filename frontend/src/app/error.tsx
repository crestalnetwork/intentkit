"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertCircle, Home, RotateCcw } from "lucide-react";

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error("Unhandled error:", error);
    }, [error]);

    return (
        <div className="container flex min-h-[60vh] flex-col items-center justify-center py-10">
            <div className="mx-auto max-w-md text-center">
                <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
                    <AlertCircle className="h-8 w-8 text-destructive" />
                </div>
                <h2 className="mb-2 text-2xl font-bold tracking-tight">
                    Something went wrong
                </h2>
                <p className="mb-6 text-muted-foreground">
                    {error.message || "An unexpected error occurred. Please try again."}
                </p>
                <div className="flex justify-center gap-3">
                    <Button variant="outline" onClick={() => reset()}>
                        <RotateCcw className="mr-2 h-4 w-4" />
                        Try Again
                    </Button>
                    <Button asChild>
                        <a href="/">
                            <Home className="mr-2 h-4 w-4" />
                            Back to Home
                        </a>
                    </Button>
                </div>
            </div>
        </div>
    );
}
