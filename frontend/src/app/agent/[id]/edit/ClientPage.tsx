"use client";
import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { agentApi } from "@/lib/api";
import { ArrowLeft } from "lucide-react";
import {
    AgentForm,
    AgentFormValues,
    projectAgentToForm,
    validateAgentForm,
} from "../../new/AgentForm";
import { cleanAgentPayload } from "../../new/formUtils";
import { toast } from "@/hooks/use-toast";
import { useAgentSlugRewrite } from "@/hooks/useAgentSlugRewrite";

export default function EditAgentPage() {
    const router = useRouter();
    const params = useParams();
    const agentId = params.id as string;

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [errors, setErrors] = useState<
        Partial<Record<keyof AgentFormValues, string>>
    >({});

    const {
        data: agent,
        isLoading: isAgentLoading,
        error: agentError,
    } = useQuery({
        queryKey: ["agent-editable", agentId],
        queryFn: () => agentApi.getEditableById(agentId),
        enabled: !!agentId,
    });

    useAgentSlugRewrite(agentId, agent?.slug);

    const resolvedId = agent?.id;

    const [values, setValues] = useState<AgentFormValues>({});

    // Seed form state once the agent has loaded (and again if it reloads).
    // Syncing during render — guarded by the last applied source — avoids an
    // effect's extra commit + cascading render.
    const [loadedAgent, setLoadedAgent] = useState<unknown>(undefined);
    if (loadedAgent !== agent) {
        setLoadedAgent(agent);
        if (agent) {
            setValues(projectAgentToForm(agent));
        }
    }

    const handleSubmit = async () => {
        const found = validateAgentForm(values);
        setErrors(found);
        if (Object.keys(found).length > 0) return;

        setIsSubmitting(true);
        setError(null);
        try {
            await agentApi.patch(resolvedId || agentId, cleanAgentPayload(values));
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

    if (isAgentLoading) {
        return (
            <div className="container py-10">
                <div className="flex justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
                </div>
            </div>
        );
    }

    if (agentError) {
        return (
            <div className="container py-10">
                <div className="text-red-500">
                    Error loading data: {(agentError as Error)?.message}
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
                <AgentForm
                    values={values}
                    onChange={setValues}
                    onSubmit={handleSubmit}
                    isSubmitting={isSubmitting}
                    submitLabel={isSubmitting ? "Saving..." : "Save Changes"}
                    readOnlyFields={["slug"]}
                    errors={errors}
                />
            </div>
        </div>
    );
}
