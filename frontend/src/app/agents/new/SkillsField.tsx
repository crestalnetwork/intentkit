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
    const { schema, formData = {}, onChange, idSchema } = props;

    const skillCategories = (schema.properties || {}) as Record<string, SkillCategorySchema>;
    const currentFormData = formData as SkillsFormData;

    // Type assertion to simplify onChange usage
    const handleChange = onChange as (data: SkillsFormData) => void;

    const handleCategoryEnabledChange = (categoryKey: string, enabled: boolean) => {
        const newFormData = {
            ...currentFormData,
            [categoryKey]: {
                ...currentFormData[categoryKey],
                enabled,
            },
        };
        handleChange(newFormData);
    };

    const handleSkillStateChange = (
        categoryKey: string,
        skillKey: string,
        value: string
    ) => {
        const newFormData = {
            ...currentFormData,
            [categoryKey]: {
                ...currentFormData[categoryKey],
                states: {
                    ...currentFormData[categoryKey]?.states,
                    [skillKey]: value,
                },
            },
        };
        handleChange(newFormData);
    };

    // Sort categories alphabetically by title
    const sortedCategories = Object.entries(skillCategories).sort(([, a], [, b]) => {
        const titleA = a.title || "";
        const titleB = b.title || "";
        return titleA.localeCompare(titleB);
    });

    return (
        <div id={idSchema?.$id || "skills-field"} className="space-y-3">
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
