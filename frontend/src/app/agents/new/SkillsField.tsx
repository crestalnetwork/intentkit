"use client";
import React from "react";
import { FieldProps } from "@rjsf/utils";
import { SkillCategoryCard } from "./SkillCategoryCard";

interface SkillCategorySchema {
    title?: string;
    description?: string;
    properties?: {
        enabled?: {
            default?: boolean;
        };
        states?: {
            properties?: Record<string, {
                title?: string;
                description?: string;
                enum?: string[];
                "x-enum-title"?: string[];
                default?: string;
            }>;
        };
    };
}

interface SkillsFormData {
    [category: string]: {
        enabled?: boolean;
        states?: Record<string, string>;
    };
}

/**
 * Custom field for rendering the entire skills object.
 * Each skill category is rendered as a collapsible card.
 */
export function SkillsField(props: FieldProps<SkillsFormData>) {
    const { schema, formData, onChange, idSchema, fieldPathId } = props;

    const skillCategories = (schema.properties || {}) as Record<string, SkillCategorySchema>;
    const currentFormData = (formData || {}) as SkillsFormData;

    const handleCategoryEnabledChange = (categoryKey: string, enabled: boolean) => {
        const newFormData = {
            ...currentFormData,
            [categoryKey]: {
                ...currentFormData[categoryKey],
                enabled,
            },
        };
        // RJSF v6 onChange signature: (newValue, path, errorSchema?, id?)
        onChange(newFormData, fieldPathId.path);
    };

    const handleSkillStateChange = (
        categoryKey: string,
        skillKey: string,
        value: string
    ) => {
        const categoryData = currentFormData[categoryKey] || {};
        const currentStates = categoryData.states || {};
        
        if (value === "disabled") {
            // When disabling, remove the skill from states using object filter
            const restStates = Object.fromEntries(
                Object.entries(currentStates).filter(([key]) => key !== skillKey)
            );
            const newFormData = {
                ...currentFormData,
                [categoryKey]: {
                    ...categoryData,
                    states: restStates,
                },
            };
            // RJSF v6 onChange signature: (newValue, path, errorSchema?, id?)
            onChange(newFormData, fieldPathId.path);
        } else {
            // When enabling (private), add the skill to states
            const newFormData = {
                ...currentFormData,
                [categoryKey]: {
                    ...categoryData,
                    states: {
                        ...currentStates,
                        [skillKey]: value,
                    },
                },
            };
            // RJSF v6 onChange signature: (newValue, path, errorSchema?, id?)
            onChange(newFormData, fieldPathId.path);
        }
    };

    // Sort categories alphabetically by title
    const sortedCategories = Object.entries(skillCategories).sort(([, a], [, b]) => {
        const titleA = a.title || "";
        const titleB = b.title || "";
        return titleA.localeCompare(titleB);
    });

    return (
        <div id={idSchema?.$id || "skills-field"} className="space-y-4">
            {/* Skills section header */}
            <div className="mb-2">
                {schema.title && (
                    <label className="block text-base font-bold mb-1">{schema.title}</label>
                )}
                {schema.description && (
                    <p className="text-xs font-normal text-muted-foreground">{schema.description}</p>
                )}
            </div>
            {sortedCategories.map(([categoryKey, categorySchema]) => {
                const categoryData = currentFormData[categoryKey] || {};
                const enabled = categoryData.enabled ?? (categorySchema.properties?.enabled?.default || false);
                const statesSchema = categorySchema.properties?.states?.properties || {};
                const statesData = categoryData.states || {};

                // Build skill state configs from schema
                const skillStates = Object.entries(statesSchema).map(([skillKey, skillSchema]) => {
                    const enumValues = skillSchema.enum || ["disabled", "public", "private"];
                    const enumTitles = skillSchema["x-enum-title"] || enumValues;

                    return {
                        title: skillSchema.title || skillKey,
                        description: skillSchema.description,
                        value: statesData[skillKey] ?? (skillSchema.default || "disabled"),
                        options: enumValues.map((val, idx) => ({
                            value: val,
                            label: enumTitles[idx] || val,
                        })),
                        onChange: (value: string) =>
                            handleSkillStateChange(categoryKey, skillKey, value),
                    };
                });

                return (
                    <SkillCategoryCard
                        key={categoryKey}
                        title={categorySchema.title || categoryKey}
                        description={categorySchema.description}
                        enabled={enabled}
                        onEnabledChange={(e) => handleCategoryEnabledChange(categoryKey, e)}
                        skillStates={skillStates}
                    />
                );
            })}
        </div>
    );
}
