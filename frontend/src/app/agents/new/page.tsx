"use client";
import React, { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { customizeValidator } from "@rjsf/validator-ajv8";
import Form, { IChangeEvent } from "@rjsf/core";
import { RJSFSchema, RegistryFieldsType } from "@rjsf/utils";
import { agentApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { widgets, BaseInputTemplate } from "./widgets";
import { templates } from "./templates";
import { SkillsField } from "./SkillsField";
import { toast } from "@/hooks/use-toast";

// Custom validator with options to handle optional fields properly
const validator = customizeValidator({
    ajvOptionsOverrides: {
        removeAdditional: true,
    },
});

// Recursively remove undefined and null values from an object
const removeEmptyValues = (obj: unknown): unknown => {
    if (obj === null || obj === undefined) {
        return undefined;
    }
    if (Array.isArray(obj)) {
        return obj.map(removeEmptyValues).filter(v => v !== undefined);
    }
    if (typeof obj === "object") {
        const result: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
            const cleaned = removeEmptyValues(value);
            if (cleaned !== undefined && cleaned !== "") {
                result[key] = cleaned;
            }
        }
        return Object.keys(result).length > 0 ? result : undefined;
    }
    return obj;
};

// Custom fields for RJSF
const fields: RegistryFieldsType = {
    SkillsField: SkillsField,
};

function generateUiSchema(schema: Record<string, unknown> | undefined) {
    const uiSchema: Record<string, unknown> = {
        "ui:title": " ", // Hide default title
        "ui:description": " ", // Hide default description
    };

    if (schema && typeof schema.properties === "object" && schema.properties !== null) {
        const properties = schema.properties as Record<string, Record<string, unknown>>;
        Object.keys(properties).forEach((key) => {
            const property = properties[key];
            const uiProperty: Record<string, unknown> = {};

            // Use custom SkillsField for skills
            if (key === "skills") {
                uiProperty["ui:field"] = "SkillsField";
            }

            if (typeof property["x-placeholder"] === "string") {
                uiProperty["ui:placeholder"] = property["x-placeholder"];
            }

            if (typeof property.maxLength === "number" && property.maxLength > 200) {
                uiProperty["ui:widget"] = "textarea";
            }

            if (Object.keys(uiProperty).length > 0) {
                uiSchema[key] = uiProperty;
            }
        });
    }

    return uiSchema;
}

export default function NewAgentPage() {
    const router = useRouter();
    const [formData, setFormData] = useState({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { data: schema, isLoading: isSchemaLoading, error: schemaError } = useQuery({
        queryKey: ["agent-schema"],
        queryFn: agentApi.getSchema,
    });

    const uiSchema = useMemo(() => generateUiSchema(schema), [schema]);

    // Clean up skills data before submission:
    // - Remove categories where enabled=false
    // - Remove skill states that are 'disabled'
    const cleanSkillsData = (data: Record<string, unknown>): Record<string, unknown> => {
        const skills = data.skills as Record<string, { enabled?: boolean; states?: Record<string, string> }> | undefined;
        if (!skills) return data;

        const cleanedSkills: Record<string, { enabled?: boolean; states?: Record<string, string> }> = {};
        for (const [categoryKey, categoryData] of Object.entries(skills)) {
            // Skip categories that are explicitly disabled
            if (categoryData.enabled === false) continue;

            // Clean up states - only keep non-disabled skills
            const states = categoryData.states || {};
            const cleanedStates: Record<string, string> = {};
            for (const [skillKey, skillValue] of Object.entries(states)) {
                if (skillValue !== 'disabled') {
                    cleanedStates[skillKey] = skillValue;
                }
            }

            // Only include category if it's enabled
            if (categoryData.enabled === true) {
                cleanedSkills[categoryKey] = {
                    enabled: true,
                    states: Object.keys(cleanedStates).length > 0 ? cleanedStates : undefined,
                };
            }
        }

        return {
            ...data,
            skills: Object.keys(cleanedSkills).length > 0 ? cleanedSkills : undefined,
        };
    };

    const handleSubmit = async ({ formData }: IChangeEvent<Record<string, unknown>>) => {
        if (!formData) return;
        setIsSubmitting(true);
        setError(null);
        try {
            const cleanedData = cleanSkillsData(formData);
            const newAgent = await agentApi.create(cleanedData);
            toast({
                title: "Agent created",
                description: "Your agent has been created successfully.",
                variant: "success",
            });
            router.push(`/agent/${newAgent.id}`);
        } catch (err) {
            console.error("Error creating agent:", err);
            setError(err instanceof Error ? err.message : "Failed to create agent");
        } finally {
            setIsSubmitting(false);
        }
    };

    const log = (type: string) => console.log.bind(console, type);

    // Transform errors to filter out optional field validation errors
    // and log validation data for debugging
    const transformErrors = useCallback(
        (errors: ReturnType<typeof validator.validateFormData>["errors"]) => {
            console.log("[RJSF Validator] Form data before validation:", JSON.stringify(formData, null, 2));
            console.log("[RJSF Validator] Schema:", JSON.stringify(schema, null, 2));
            console.log("[RJSF Validator] Raw validation errors:", errors);
            
            // Get required fields from schema
            const requiredFields = (schema?.required as string[]) || [];
            
            // Filter out errors for optional fields with empty/undefined values
            const filteredErrors = errors.filter((error) => {
                // Extract field name from the error property path
                const fieldName = error.property?.replace(/^\./, "").split(".")[0] || "";
                
                // If the field is required, keep the error
                if (requiredFields.includes(fieldName)) {
                    return true;
                }
                
                // If the error is about type mismatch for an optional field
                // and the value is empty/undefined, filter it out
                if (error.name === "type") {
                    const fieldValue = (formData as Record<string, unknown>)[fieldName];
                    if (fieldValue === undefined || fieldValue === null || fieldValue === "") {
                        console.log(`[RJSF Validator] Filtering out type error for optional empty field: ${fieldName}`);
                        return false;
                    }
                }
                
                return true;
            });
            
            console.log("[RJSF Validator] Filtered errors:", filteredErrors);
            return filteredErrors;
        },
        [formData, schema]
    );

    if (isSchemaLoading) {
        return (
            <div className="container py-10">
                <div className="flex justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
                </div>
            </div>
        );
    }

    if (schemaError) {
        return (
            <div className="container py-10">
                <div className="text-red-500">
                    Error loading schema: {(schemaError as Error).message}
                </div>
            </div>
        );
    }

    return (
        <div className="container py-10 max-w-3xl">
            <div className="mb-8">
                <Link
                    href="/"
                    className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
                >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to Agents
                </Link>
                <h1 className="text-3xl font-bold tracking-tight">Create New Agent</h1>
                <p className="text-muted-foreground mt-2">
                    Configure your new autonomous agent.
                </p>
            </div>

            <div className="bg-card rounded-lg border shadow-sm p-6">
                {error && (
                    <div className="bg-destructive/10 text-destructive p-3 rounded-md mb-4 text-sm">
                        {error}
                    </div>
                )}
                <Form
                    schema={schema as RJSFSchema}
                    uiSchema={uiSchema}
                    validator={validator}
                    formData={formData}
                    onChange={(e) => setFormData(e.formData || {})}
                    onSubmit={handleSubmit}
                    onError={log("errors")}
                    transformErrors={transformErrors}
                    className="space-y-6"
                    widgets={widgets}
                    fields={fields}
                    templates={{ ...templates, BaseInputTemplate }}
                >
                    <div className="flex justify-end pt-4">
                        <Button type="submit" disabled={isSubmitting}>
                            {isSubmitting ? "Creating..." : "Create Agent"}
                        </Button>
                    </div>
                </Form>
            </div>
        </div>
    );
}
