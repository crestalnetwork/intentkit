"use client";
import React from "react";
import { FieldProps } from "@rjsf/utils";
import { ToolsetCard } from "./ToolsetCard";
import { config } from "@/lib/config";

interface ToolInfo {
    title?: string;
    description?: string;
}

interface ToolsetCatalogEntry {
    title?: string;
    description?: string;
    "x-icon"?: string;
    tools?: Record<string, ToolInfo>;
}

/**
 * Custom field for the agent tools list.
 *
 * The form value is a flat list of enabled tool names; the toolset catalog
 * (categories with their tools) comes from the schema's `x-catalog`.
 */
export function ToolsField(props: FieldProps<string[]>) {
    const { schema, formData, onChange, idSchema, fieldPathId } = props;

    const catalog = ((schema as Record<string, unknown>)["x-catalog"] ||
        {}) as Record<string, ToolsetCatalogEntry>;
    const selected = new Set(formData || []);

    const setSelected = (next: Set<string>) => {
        onChange(Array.from(next), fieldPathId.path);
    };

    const handleToolToggle = (toolKey: string, enabled: boolean) => {
        const next = new Set(selected);
        if (enabled) {
            next.add(toolKey);
        } else {
            next.delete(toolKey);
        }
        setSelected(next);
    };

    const handleCategoryClear = (categoryKey: string) => {
        const tools = catalog[categoryKey]?.tools || {};
        const next = new Set(selected);
        for (const toolKey of Object.keys(tools)) {
            next.delete(toolKey);
        }
        setSelected(next);
    };

    // Sort toolsets alphabetically by title
    const sortedCategories = Object.entries(catalog).sort(([, a], [, b]) => {
        const titleA = a.title || "";
        const titleB = b.title || "";
        return titleA.localeCompare(titleB);
    });

    return (
        <div id={idSchema?.$id || "tools-field"} className="space-y-4">
            {/* Tools section header */}
            <div className="mb-2">
                {schema.title && (
                    <label className="block text-base font-bold mb-1">{schema.title}</label>
                )}
                {schema.description && (
                    <p className="text-xs font-normal text-muted-foreground">{schema.description}</p>
                )}
            </div>
            {sortedCategories.map(([categoryKey, categorySchema]) => {
                const tools = Object.entries(categorySchema.tools || {}).map(
                    ([toolKey, toolInfo]) => ({
                        title: toolInfo.title || toolKey,
                        description: toolInfo.description,
                        enabled: selected.has(toolKey),
                        onToggle: (enabled: boolean) =>
                            handleToolToggle(toolKey, enabled),
                    })
                );

                // Build icon URL: relative paths get API base prefix, absolute URLs pass through
                const rawIcon = categorySchema["x-icon"];
                const iconUrl = rawIcon
                    ? rawIcon.startsWith("/")
                        ? `${config.apiBaseUrl}${rawIcon}`
                        : rawIcon
                    : undefined;

                return (
                    <ToolsetCard
                        key={categoryKey}
                        title={categorySchema.title || categoryKey}
                        description={categorySchema.description}
                        iconUrl={iconUrl}
                        tools={tools}
                        onClear={() => handleCategoryClear(categoryKey)}
                    />
                );
            })}
        </div>
    );
}
