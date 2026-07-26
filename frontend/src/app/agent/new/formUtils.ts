import type { AgentFormValues } from "./AgentForm";

/**
 * Normalise form state into an API payload.
 *
 * Drops empty strings and empty arrays so the server sees "unset" rather than
 * "set to blank", and de-duplicates the tool list.
 */
export function cleanAgentPayload(
    values: AgentFormValues,
): Record<string, unknown> {
    const payload: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(values)) {
        if (value === undefined || value === null) continue;
        if (typeof value === "string" && value.trim() === "") continue;
        if (Array.isArray(value)) {
            const unique = Array.from(new Set(value));
            if (unique.length === 0) continue;
            payload[key] = unique;
            continue;
        }
        payload[key] = value;
    }

    return payload;
}
