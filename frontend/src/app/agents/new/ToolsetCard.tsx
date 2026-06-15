"use client";
import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface ToolStateOption {
    value: string;
    label: string;
}

interface ToolStateConfig {
    title: string;
    description?: string;
    value: string;
    options: ToolStateOption[];
    onChange: (value: string) => void;
}

interface ToolsetCardProps {
    title: string;
    description?: string;
    iconUrl?: string;
    enabled: boolean;
    onEnabledChange: (enabled: boolean) => void;
    toolStates: ToolStateConfig[];
    defaultExpanded?: boolean;
}

export function ToolsetCard({
    title,
    description,
    iconUrl,
    enabled,
    onEnabledChange,
    toolStates,
    defaultExpanded = false,
}: ToolsetCardProps) {
    const [isExpanded, setIsExpanded] = useState(enabled || defaultExpanded);
    const [prevEnabled, setPrevEnabled] = useState(enabled);

    // Auto-expand when enabled, auto-collapse when disabled. Adjusting during
    // render (instead of in an effect) avoids an extra commit + cascading render.
    if (enabled !== prevEnabled) {
        setPrevEnabled(enabled);
        setIsExpanded(enabled);
    }

    // Count active tools (those not set to "disabled")
    const activeToolsCount = toolStates.filter(
        (tool) => tool.value !== "disabled"
    ).length;

    return (
        <div className="border rounded-lg bg-card shadow-xs overflow-hidden">
            {/* Header */}
            <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-3">
                    <button
                        type="button"
                        className="text-muted-foreground"
                        aria-label={isExpanded ? "Collapse" : "Expand"}
                    >
                        {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                    </button>
                    {iconUrl && (
                        <img
                            src={iconUrl}
                            alt={title}
                            className="h-6 w-6 rounded object-contain"
                        />
                    )}
                    <div>
                        <h3 className="font-semibold text-sm">{title}</h3>
                        {description && (
                            <p className="text-xs font-normal text-muted-foreground line-clamp-1">
                                {description}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {enabled && activeToolsCount > 0 && (
                        <span className="text-xs text-muted-foreground">
                            {activeToolsCount} active
                        </span>
                    )}
                    <label
                        className="relative inline-flex items-center cursor-pointer"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <input
                            type="checkbox"
                            className="sr-only peer"
                            checked={enabled}
                            onChange={(e) => onEnabledChange(e.target.checked)}
                        />
                        <div className="w-9 h-5 bg-muted rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-primary after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                </div>
            </div>

            {/* Expanded Content */}
            {isExpanded && enabled && toolStates.length > 0 && (
                <div className="px-4 pb-4 pt-2 border-t bg-muted/30">
                    <div className="grid gap-3">
                        {toolStates.map((tool, index) => (
                            <div
                                key={index}
                                className="flex items-center justify-between gap-4"
                            >
                            <div className="flex-1 min-w-0">
                                    <label className="text-xs font-semibold">
                                        {tool.title}
                                    </label>
                                    {tool.description && (
                                        <p className="text-xs font-normal text-muted-foreground line-clamp-1">
                                            {tool.description}
                                        </p>
                                    )}
                                </div>
                                {/* Checkbox: checked = private/public, unchecked = disabled */}
                                <label
                                    className="relative inline-flex items-center cursor-pointer"
                                >
                                    <input
                                        type="checkbox"
                                        className="sr-only peer"
                                        checked={tool.value === "private" || tool.value === "public"}
                                        onChange={(e) => tool.onChange(e.target.checked ? "private" : "disabled")}
                                    />
                                    <div className="w-9 h-5 bg-muted rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-primary after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                                </label>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Collapsed hint when disabled */}
            {isExpanded && !enabled && (
                <div className="px-4 pb-4 pt-2 border-t bg-muted/30">
                    <p className="text-xs text-muted-foreground italic">
                        Enable this toolset to configure individual tools.
                    </p>
                </div>
            )}
        </div>
    );
}
