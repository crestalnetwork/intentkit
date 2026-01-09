"use client";
import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface SkillStateOption {
    value: string;
    label: string;
}

interface SkillStateConfig {
    title: string;
    description?: string;
    value: string;
    options: SkillStateOption[];
    onChange: (value: string) => void;
}

interface SkillCategoryCardProps {
    title: string;
    description?: string;
    enabled: boolean;
    onEnabledChange: (enabled: boolean) => void;
    skillStates: SkillStateConfig[];
    defaultExpanded?: boolean;
}

export function SkillCategoryCard({
    title,
    description,
    enabled,
    onEnabledChange,
    skillStates,
    defaultExpanded = false,
}: SkillCategoryCardProps) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    // Count active skills (those not set to "disabled")
    const activeSkillsCount = skillStates.filter(
        (skill) => skill.value !== "disabled"
    ).length;

    return (
        <div className="border rounded-lg bg-card shadow-sm overflow-hidden">
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
                    <div>
                        <h3 className="font-semibold text-sm">{title}</h3>
                        {description && (
                            <p className="text-xs text-muted-foreground line-clamp-1">
                                {description}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {enabled && activeSkillsCount > 0 && (
                        <span className="text-xs text-muted-foreground">
                            {activeSkillsCount} active
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
            {isExpanded && enabled && skillStates.length > 0 && (
                <div className="px-4 pb-4 pt-2 border-t bg-muted/30">
                    <div className="grid gap-3">
                        {skillStates.map((skill, index) => (
                            <div
                                key={index}
                                className="flex items-center justify-between gap-4"
                            >
                                <div className="flex-1 min-w-0">
                                    <label className="text-sm font-medium">
                                        {skill.title}
                                    </label>
                                    {skill.description && (
                                        <p className="text-xs text-muted-foreground line-clamp-1">
                                            {skill.description}
                                        </p>
                                    )}
                                </div>
                                <select
                                    value={skill.value}
                                    onChange={(e) => skill.onChange(e.target.value)}
                                    className="h-8 px-2 text-xs rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring min-w-[120px]"
                                >
                                    {skill.options.map((opt) => (
                                        <option key={opt.value} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Collapsed hint when disabled */}
            {isExpanded && !enabled && (
                <div className="px-4 pb-4 pt-2 border-t bg-muted/30">
                    <p className="text-xs text-muted-foreground italic">
                        Enable this skill category to configure individual skills.
                    </p>
                </div>
            )}
        </div>
    );
}
