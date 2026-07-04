"use client";
import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface ToolToggleConfig {
    title: string;
    description?: string;
    enabled: boolean;
    onToggle: (enabled: boolean) => void;
}

interface ToolsetCardProps {
    title: string;
    description?: string;
    iconUrl?: string;
    tools: ToolToggleConfig[];
    onClear: () => void;
    defaultExpanded?: boolean;
}

export function ToolsetCard({
    title,
    description,
    iconUrl,
    tools,
    onClear,
    defaultExpanded = false,
}: ToolsetCardProps) {
    const activeToolsCount = tools.filter((tool) => tool.enabled).length;
    const [isExpanded, setIsExpanded] = useState(
        activeToolsCount > 0 || defaultExpanded
    );

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
                    {activeToolsCount > 0 && (
                        <span className="text-xs text-muted-foreground">
                            {activeToolsCount} active
                        </span>
                    )}
                    {activeToolsCount > 0 && (
                        <button
                            type="button"
                            className="text-xs text-muted-foreground hover:text-foreground underline"
                            onClick={(e) => {
                                e.stopPropagation();
                                onClear();
                            }}
                        >
                            Clear
                        </button>
                    )}
                </div>
            </div>

            {/* Expanded Content */}
            {isExpanded && tools.length > 0 && (
                <div className="px-4 pb-4 pt-2 border-t bg-muted/30">
                    <div className="grid gap-3">
                        {tools.map((tool, index) => (
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
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        className="sr-only peer"
                                        checked={tool.enabled}
                                        onChange={(e) => tool.onToggle(e.target.checked)}
                                    />
                                    <div className="w-9 h-5 bg-muted rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-primary after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                                </label>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
