"use client";
import React, { useState, useMemo, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { customizeValidator } from "@rjsf/validator-ajv8";
import Form, { IChangeEvent } from "@rjsf/core";
import { RJSFSchema, RegistryFieldsType } from "@rjsf/utils";
import { agentApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { widgets, BaseInputTemplate } from "../../new/widgets";
import { templates } from "../../new/templates";
import { SkillsField } from "../../new/SkillsField";

// Custom validator with options to handle optional fields properly
const validator = customizeValidator({
    ajvOptionsOverrides: {
        removeAdditional: true,
    },
});

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

            // Make id field read-only in edit mode
            if (key === "id") {
                uiProperty["ui:readonly"] = true;
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

export default function EditAgentPage() {
    const router = useRouter();
    const params = useParams();
    const agentId = params.id as string;
    
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch the agent schema
    const { data: schema, isLoading: isSchemaLoading, error: schemaError } = useQuery({
        queryKey: ["agent-schema"],
        queryFn: agentApi.getSchema,
    });

    // Fetch the existing agent data
    const { data: agent, isLoading: isAgentLoading, error: agentError } = useQuery({
        queryKey: ["agent", agentId],
        queryFn: () => agentApi.getById(agentId),
        enabled: !!agentId,
    });

    // Filter agent data to only include fields defined in the schema
    const filterBySchema = (
        agentData: Record<string, unknown>,
        schemaData: Record<string, unknown>
    ): Record<string, unknown> => {
        if (!schemaData.properties || typeof schemaData.properties !== "object") {
            return {};
        }
        const schemaProperties = schemaData.properties as Record<string, unknown>;
        const filtered: Record<string, unknown> = {};
        
        for (const key of Object.keys(schemaProperties)) {
            if (key in agentData) {
                filtered[key] = agentData[key];
            }
        }
        
        return filtered;
    };

    // Initialize formData from agent data, filtered by schema
    const [formData, setFormData] = useState<Record<string, unknown>>({});
    
    // Update formData when agent data and schema are loaded
    React.useEffect(() => {
        if (agent && schema) {
            const filteredData = filterBySchema(
                agent as unknown as Record<string, unknown>,
                schema
            );
            setFormData(filteredData);
        }
    }, [agent, schema]);

    const uiSchema = useMemo(() => generateUiSchema(schema), [schema]);

    // Clean up skills data before submission:
    // - Remove categories where enabled=false
    // - Remove skill states that are 'disabled'
    // - Remove skills that are not defined in the schema (handles renamed skills)
    const cleanSkillsData = (data: Record<string, unknown>, schemaData: Record<string, unknown> | undefined): Record<string, unknown> => {
        const skills = data.skills as Record<string, { enabled?: boolean; states?: Record<string, string> }> | undefined;
        if (!skills) return data;

        // Extract valid skill keys from the schema for each category
        const getValidSkillsForCategory = (categoryKey: string): Set<string> | null => {
            if (!schemaData?.properties) return null;
            const schemaProperties = schemaData.properties as Record<string, Record<string, unknown>>;
            const skillsSchema = schemaProperties.skills;
            if (!skillsSchema?.properties) return null;
            const skillsCategoriesSchema = skillsSchema.properties as Record<string, Record<string, unknown>>;
            const categorySchema = skillsCategoriesSchema[categoryKey];
            if (!categorySchema?.properties) return null;
            const categoryProperties = categorySchema.properties as Record<string, Record<string, unknown>>;
            const statesSchema = categoryProperties.states;
            if (!statesSchema?.properties) return null;
            const statesProperties = statesSchema.properties as Record<string, unknown>;
            return new Set(Object.keys(statesProperties));
        };

        // Extract valid category keys from the schema
        const getValidCategories = (): Set<string> | null => {
            if (!schemaData?.properties) return null;
            const schemaProperties = schemaData.properties as Record<string, Record<string, unknown>>;
            const skillsSchema = schemaProperties.skills;
            if (!skillsSchema?.properties) return null;
            const skillsCategoriesSchema = skillsSchema.properties as Record<string, unknown>;
            return new Set(Object.keys(skillsCategoriesSchema));
        };

        const validCategories = getValidCategories();
        const cleanedSkills: Record<string, { enabled?: boolean; states?: Record<string, string> }> = {};
        for (const [categoryKey, categoryData] of Object.entries(skills)) {
            // Skip categories that are explicitly disabled
            if (categoryData.enabled === false) continue;

            // Skip categories not in schema (removed categories)
            if (validCategories && !validCategories.has(categoryKey)) {
                console.log(`[cleanSkillsData] Removing category not in schema: ${categoryKey}`);
                continue;
            }

            // Get valid skills for this category
            const validSkills = getValidSkillsForCategory(categoryKey);

            // Clean up states - only keep non-disabled skills that exist in schema
            const states = categoryData.states || {};
            const cleanedStates: Record<string, string> = {};
            for (const [skillKey, skillValue] of Object.entries(states)) {
                // Skip disabled skills
                if (skillValue === 'disabled') continue;
                
                // Skip skills not in schema (old/renamed skills)
                if (validSkills && !validSkills.has(skillKey)) {
                    console.log(`[cleanSkillsData] Removing skill not in schema: ${categoryKey}.${skillKey}`);
                    continue;
                }
                
                cleanedStates[skillKey] = skillValue;
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
            const cleanedData = cleanSkillsData(formData, schema);
            await agentApi.patch(agentId, cleanedData);
            router.push("/");
        } catch (err) {
            console.error("Error updating agent:", err);
            setError(err instanceof Error ? err.message : "Failed to update agent");
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

    if (isSchemaLoading || isAgentLoading) {
        return (
            <div className="container py-10">
                <div className="flex justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
                </div>
            </div>
        );
    }

    if (schemaError || agentError) {
        return (
            <div className="container py-10">
                <div className="text-red-500">
                    Error loading data: {(schemaError as Error)?.message || (agentError as Error)?.message}
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
                <h1 className="text-3xl font-bold tracking-tight">Edit Agent</h1>
                <p className="text-muted-foreground mt-2">
                    Modify your agent configuration.
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
                            {isSubmitting ? "Saving..." : "Save Changes"}
                        </Button>
                    </div>
                </Form>
            </div>
        </div>
    );
}
