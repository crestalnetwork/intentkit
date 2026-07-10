"use client";
import React, { useId, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface AdvancedSectionProps {
    title?: string;
    defaultOpen?: boolean;
    bodyClassName?: string;
    children: React.ReactNode;
}

/** Collapsed disclosure section used across the agent form. */
export function AdvancedSection({
    title = "Advanced Settings",
    defaultOpen = false,
    bodyClassName,
    children,
}: AdvancedSectionProps) {
    const [open, setOpen] = useState(defaultOpen);
    const bodyId = useId();

    return (
        <div className="border-t pt-2 mt-4">
            <button
                type="button"
                aria-expanded={open}
                aria-controls={open ? bodyId : undefined}
                onClick={() => setOpen(!open)}
                className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
            >
                {open ? (
                    <ChevronDown className="h-4 w-4" />
                ) : (
                    <ChevronRight className="h-4 w-4" />
                )}
                {title}
            </button>
            {open && (
                <div id={bodyId} className={bodyClassName}>
                    {children}
                </div>
            )}
        </div>
    );
}
