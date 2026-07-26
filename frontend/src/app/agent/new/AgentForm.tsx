"use client";

import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { metadataApi } from "@/lib/api";
import {
    CheckboxField,
    FieldShell,
    Section,
    SelectField,
    TextAreaField,
    TextField,
} from "./fields";
import { ModelSelectField } from "./ModelSelectField";
import { PictureField } from "./PictureField";
import { StringArrayField } from "./StringArrayField";
import { ToolCatalog, ToolsField } from "./ToolsField";

/**
 * The agent form.
 *
 * Every field is declared here by hand. This used to be generated from the
 * backend's JSON schema (`GET /schema/agent` + RJSF), which meant field labels,
 * help text and validation lived in the backend and had to be kept in sync with
 * a hand-maintained schema.json. Editing a field is now a single change in this
 * file, next to the backend model change it accompanies.
 *
 * The only runtime data still fetched is what genuinely varies per deployment:
 * the LLM list (`/metadata/llms`, inside ModelSelectField) and the toolset
 * catalog (`/metadata/tools`).
 *
 * Constraints below mirror `AgentUpdate` in intentkit/models/agent/user_input.py.
 * The server is authoritative; these exist to fail fast in the UI.
 */

export interface AgentFormValues {
    name?: string;
    slug?: string;
    picture?: string;
    description?: string;
    model?: string;
    reasoning_effort?: string;
    system_prompt?: string;
    search_internet?: boolean;
    enable_activity?: boolean;
    enable_post?: boolean;
    tools?: string[];
    sub_agents?: string[];
    sub_agent_prompt?: string;
}

/** Keys this form owns, used to project an API agent onto form state.
 *
 * `satisfies` makes this exhaustive: adding a field to AgentFormValues without
 * listing it here is a type error, rather than a field the edit form silently
 * drops. */
const FORM_KEYS = Object.keys({
    name: 0,
    slug: 0,
    picture: 0,
    description: 0,
    model: 0,
    reasoning_effort: 0,
    system_prompt: 0,
    search_internet: 0,
    enable_activity: 0,
    enable_post: 0,
    tools: 0,
    sub_agents: 0,
    sub_agent_prompt: 0,
} satisfies Record<keyof AgentFormValues, unknown>) as (keyof AgentFormValues)[];

/** Reasoning levels are clamped per model server-side (see llm.yaml). */
const REASONING_EFFORTS = [
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
] as const;

// Level 1 headings are reserved for our own prompt assembly. Mirrors the
// validators on AgentUpdate.system_prompt / .sub_agent_prompt.
const NO_H1 = /^(([^#].*)|#[^# ].*|#{2,}[ ].*|$)(\n(([^#].*)|#[^# ].*|#{2,}[ ].*|$))*$/;
const NO_H1_H2 = /^(([^#].*)|#[^# ].*|#{3,}[ ].*|$)(\n(([^#].*)|#[^# ].*|#{3,}[ ].*|$))*$/;

const SLUG_PATTERN = /^[a-z]([a-z0-9-]*[a-z0-9])?$/;

export function projectAgentToForm(agent: object): AgentFormValues {
    const source = agent as Record<string, unknown>;
    const values: Record<string, unknown> = {};
    for (const key of FORM_KEYS) {
        if (key in source && source[key] !== null) {
            values[key] = source[key];
        }
    }
    return values as AgentFormValues;
}

export function validateAgentForm(
    values: AgentFormValues,
): Partial<Record<keyof AgentFormValues, string>> {
    const errors: Partial<Record<keyof AgentFormValues, string>> = {};

    if (!values.name?.trim()) {
        errors.name = "Agent name is required";
    } else if (values.name.length > 50) {
        errors.name = "Must be at most 50 characters";
    }

    if (values.slug) {
        if (values.slug.length < 2 || values.slug.length > 60) {
            errors.slug = "Must be between 2 and 60 characters";
        } else if (!SLUG_PATTERN.test(values.slug)) {
            errors.slug =
                "Must start with a letter and contain only lowercase letters, numbers and hyphens";
        }
    }

    if (values.system_prompt) {
        if (values.system_prompt.length > 200000) {
            errors.system_prompt = "Must be at most 200000 characters";
        } else if (!NO_H1.test(values.system_prompt)) {
            errors.system_prompt =
                "Level 1 headings (#) are not allowed. Use level 2+ headings (##, ###) instead.";
        }
    }

    if (values.sub_agent_prompt) {
        if (values.sub_agent_prompt.length > 20000) {
            errors.sub_agent_prompt = "Must be at most 20000 characters";
        } else if (!NO_H1_H2.test(values.sub_agent_prompt)) {
            errors.sub_agent_prompt =
                "Level 1 and 2 headings (# and ##) are not allowed. Use level 3+ headings (###, ####) instead.";
        }
    }

    return errors;
}

interface AgentFormProps {
    values: AgentFormValues;
    onChange: (values: AgentFormValues) => void;
    onSubmit: () => void;
    isSubmitting: boolean;
    submitLabel: string;
    /** Fields the server refuses to change after creation. */
    readOnlyFields?: (keyof AgentFormValues)[];
    errors?: Partial<Record<keyof AgentFormValues, string>>;
}

export function AgentForm({
    values,
    onChange,
    onSubmit,
    isSubmitting,
    submitLabel,
    readOnlyFields = [],
    errors = {},
}: AgentFormProps) {
    const { data: catalog, error: toolCatalogError } = useQuery<ToolCatalog>({
        queryKey: ["tool-catalog"],
        queryFn: async () => (await metadataApi.getToolCatalog()) as ToolCatalog,
        staleTime: 60 * 60 * 1000,
    });

    const isReadOnly = (key: keyof AgentFormValues) => readOnlyFields.includes(key);
    const set = <K extends keyof AgentFormValues>(
        key: K,
        value: AgentFormValues[K],
    ) => onChange({ ...values, [key]: value });

    return (
        <form
            onSubmit={(e) => {
                e.preventDefault();
                onSubmit();
            }}
        >
            <Section title="Basic">
                <TextField
                    id="name"
                    label="Agent Name"
                    description="Display name of the agent"
                    placeholder="Enter agent name"
                    value={values.name ?? ""}
                    onChange={(v) => set("name", v)}
                    required
                    maxLength={50}
                    disabled={isSubmitting}
                    error={errors.name}
                />
                <TextField
                    id="slug"
                    label="Slug"
                    description="URL-friendly identifier. Must start with a letter. Lowercase letters, numbers, and hyphens only. Cannot be changed once set."
                    placeholder="e.g. my-agent"
                    value={values.slug ?? ""}
                    onChange={(v) => set("slug", v)}
                    maxLength={60}
                    disabled={isSubmitting || isReadOnly("slug")}
                    error={errors.slug}
                />
                <FieldShell id="picture" label="Picture" description="Picture of the agent">
                    <PictureField
                        id="picture"
                        value={values.picture ?? ""}
                        onChange={(v) => set("picture", v)}
                        disabled={isSubmitting}
                    />
                </FieldShell>
                <TextAreaField
                    id="description"
                    label="Description"
                    description="Short public summary of what the agent does, shown in agent listings and used to describe it when wired as a sub-agent. Not injected into the agent's own prompt."
                    placeholder="Introduce your agent"
                    value={values.description ?? ""}
                    onChange={(v) => set("description", v)}
                    rows={3}
                    disabled={isSubmitting}
                    error={errors.description}
                />
            </Section>

            <Section title="LLM">
                <FieldShell
                    id="model"
                    label="AI Model"
                    description="Select the LLM for your agent. Note that each LLM has its specific advantages, behaviour and cost."
                >
                    <ModelSelectField
                        id="model"
                        value={values.model}
                        onChange={(v) => set("model", v)}
                        disabled={isSubmitting}
                    />
                </FieldShell>
                <SelectField
                    id="reasoning_effort"
                    label="Reasoning Effort"
                    description="How much thinking the model does before answering. Leave unset to use the model's recommended default; the value is automatically adapted to the levels the selected model supports. Higher effort improves hard-task quality but costs more and responds slower."
                    value={values.reasoning_effort ?? ""}
                    onChange={(v) => set("reasoning_effort", v || undefined)}
                    options={REASONING_EFFORTS.map((e) => ({ value: e, label: e }))}
                    placeholder="Model default"
                    disabled={isSubmitting}
                />
                <TextAreaField
                    id="system_prompt"
                    label="System Prompt"
                    description="Define the agent's purpose, personality, principles, knowledge, and behavior. Markdown is supported; organize sections with level 2+ headings (##, ###)."
                    placeholder="Enter the agent system prompt"
                    value={values.system_prompt ?? ""}
                    onChange={(v) => set("system_prompt", v)}
                    rows={12}
                    disabled={isSubmitting}
                    error={errors.system_prompt}
                />
                <CheckboxField
                    id="search_internet"
                    label="Internet Search"
                    description="Enable LLM native internet search for this agent"
                    checked={values.search_internet ?? true}
                    onChange={(v) => set("search_internet", v)}
                    disabled={isSubmitting}
                />
                <CheckboxField
                    id="enable_activity"
                    label="Activity Publishing"
                    description="Enable activity tools (create activity, recent activities)"
                    checked={values.enable_activity ?? true}
                    onChange={(v) => set("enable_activity", v)}
                    disabled={isSubmitting}
                />
                <CheckboxField
                    id="enable_post"
                    label="Post Publishing"
                    description="Enable post tools (create post, get post, recent posts)"
                    checked={values.enable_post ?? true}
                    onChange={(v) => set("enable_post", v)}
                    disabled={isSubmitting}
                />
            </Section>

            <Section title="Tools">
                {toolCatalogError ? (
                    <p className="mb-4 text-sm text-destructive">
                        Could not load the tool catalog:{" "}
                        {(toolCatalogError as Error).message}
                    </p>
                ) : (
                    <FieldShell
                        id="tools-field"
                        label="Tools"
                        description="List of enabled tool names. Please choose the Agent's tools carefully. Excessive tools will pollute the context and reduce the Agent's intelligence. Only select the necessary tools, and it is best not to exceed 10."
                    >
                        <ToolsField
                            value={values.tools}
                            onChange={(v) => set("tools", v)}
                            catalog={catalog ?? {}}
                        />
                    </FieldShell>
                )}
                <FieldShell
                    id="sub_agents"
                    label="Sub-Agents"
                    description="List of sub-agent IDs or slugs that this agent can call using the call_agent tool. Only listed agents can be called."
                >
                    <StringArrayField
                        id="sub_agents"
                        value={values.sub_agents}
                        onChange={(v) => set("sub_agents", v)}
                        disabled={isSubmitting}
                    />
                </FieldShell>
                <TextAreaField
                    id="sub_agent_prompt"
                    label="Sub-Agent Instructions"
                    description="Additional instructions for how the agent should use its sub-agents"
                    value={values.sub_agent_prompt ?? ""}
                    onChange={(v) => set("sub_agent_prompt", v)}
                    rows={6}
                    disabled={isSubmitting}
                    error={errors.sub_agent_prompt}
                />
            </Section>

            <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {submitLabel}
            </Button>
        </form>
    );
}
