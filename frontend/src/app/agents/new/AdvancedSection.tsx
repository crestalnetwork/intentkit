"use client";
import React, { useId, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface AdvancedSectionProps {
    defaultOpen?: boolean;
    bodyClassName?: string;
    children: React.ReactNode;
}

/** Collapsed "Advanced Settings" disclosure used across the agent form. */
export function AdvancedSection({
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
                aria-controls={bodyId}
                onClick={() => setOpen(!open)}
                className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
            >
                {open ? (
                    <ChevronDown className="h-4 w-4" />
                ) : (
                    <ChevronRight className="h-4 w-4" />
                )}
                Advanced Settings
            </button>
            {open && (
                <div id={bodyId} className={bodyClassName}>
                    {children}
                </div>
            )}
        </div>
    );
}
