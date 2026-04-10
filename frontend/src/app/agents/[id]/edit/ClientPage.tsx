"use client";
import React, { useState, useMemo, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import Form, { IChangeEvent } from "@rjsf/core";
import { RJSFSchema } from "@rjsf/utils";
import { agentApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { widgets, BaseInputTemplate } from "../../new/widgets";
import { templates } from "../../new/templates";
import {
    validator,
    fields,
    onFormError,
    generateUiSchema,
    createTransformErrors,
    cleanSkillsData,
    filterBySchema,
} from "../../new/formUtils";
import { toast } from "@/hooks/use-toast";

const SCHEMA_STALE_TIME = 5 * 60 * 1000;

export default function EditAgentPage() {
    const router = useRouter();
    const params = useParams();
    const agentId = params.id as string;

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { data: schema, isLoading: isSchemaLoading, error: schemaError } = useQuery({
        queryKey: ["agent-schema"],
        queryFn: agentApi.getSchema,
        staleTime: SCHEMA_STALE_TIME,
    });

    const { data: agent, isLoading: isAgentLoading, error: agentError } = useQuery({
        queryKey: ["agent-editable", agentId],
        queryFn: () => agentApi.getEditableById(agentId),
        enabled: !!agentId,
    });

    const resolvedId = (agent as Record<string, unknown> | undefined)?.id as string | undefined;

    const [formData, setFormData] = useState<Record<string, unknown>>({});

    React.useEffect(() => {
        if (agent && schema) {
            const filteredData = filterBySchema(
                agent as unknown as Record<string, unknown>,
                schema
            );
            setFormData(filteredData);
        }
    }, [agent, schema]);

    const uiSchema = useMemo(() => generateUiSchema(schema, ["id", "slug"]), [schema]);

    const handleSubmit = async ({ formData }: IChangeEvent<Record<string, unknown>>) => {
        if (!formData) return;
        setIsSubmitting(true);
        setError(null);
        try {
            const cleanedData = cleanSkillsData(formData, schema);
            await agentApi.patch(resolvedId || agentId, cleanedData);
            toast({
                title: "Agent updated",
                description: "Your agent has been updated successfully.",
                variant: "success",
            });
            router.push(`/agent/${agentId}`);
        } catch (err) {
            console.error("Error updating agent:", err);
            setError(err instanceof Error ? err.message : "Failed to update agent");
        } finally {
            setIsSubmitting(false);
        }
    };

    const transformErrors = useCallback(
        () => createTransformErrors(formData, schema),
        [formData, schema]
    )();

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
                    href="/agents"
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

            <div className="bg-card rounded-lg border shadow-xs p-6">
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
                    onError={onFormError}
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
