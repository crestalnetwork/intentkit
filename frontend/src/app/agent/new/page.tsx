"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { agentApi } from "@/lib/api";
import { ArrowLeft } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import {
    AgentForm,
    AgentFormValues,
    validateAgentForm,
} from "./AgentForm";
import { cleanAgentPayload } from "./formUtils";

export default function NewAgentPage() {
    const router = useRouter();
    const [values, setValues] = useState<AgentFormValues>({});
    const [errors, setErrors] = useState<
        Partial<Record<keyof AgentFormValues, string>>
    >({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async () => {
        const found = validateAgentForm(values);
        setErrors(found);
        if (Object.keys(found).length > 0) return;

        setIsSubmitting(true);
        setError(null);
        try {
            const newAgent = await agentApi.create(cleanAgentPayload(values, "create"));
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
                <h1 className="text-3xl font-bold tracking-tight">Create New Agent</h1>
                <p className="text-muted-foreground mt-2">
                    Configure your new autonomous agent.
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
                    submitLabel={isSubmitting ? "Creating..." : "Create Agent"}
                    errors={errors}
                />
            </div>
        </div>
    );
}
