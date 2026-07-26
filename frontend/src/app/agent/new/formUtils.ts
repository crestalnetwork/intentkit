import type { AgentFormValues } from "./AgentForm";

/**
 * Normalise form state into an API payload.
 *
 * The two modes differ in how they treat emptiness, because PATCH applies
 * `model_dump(exclude_unset=True)` server-side: an omitted key means "leave
 * alone", so an edit that clears a field has to send the empty value rather
 * than drop it, or the change silently does nothing.
 *
 * - "create": drop empties so the server's own defaults apply.
 * - "edit":   keep empties so clearing a field actually clears it.
 *
 * Tool and sub-agent names are de-duplicated either way; the server drops
 * unknown ones (see sanitize_tools).
 */
export function cleanAgentPayload(
    values: AgentFormValues,
    mode: "create" | "edit",
): Record<string, unknown> {
    const payload: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(values)) {
        if (value === undefined || value === null) continue;

        if (Array.isArray(value)) {
            const unique = Array.from(new Set(value));
            if (unique.length === 0 && mode === "create") continue;
            payload[key] = unique;
            continue;
        }

        if (typeof value === "string" && value.trim() === "") {
            if (mode === "create") continue;
            payload[key] = "";
            continue;
        }

        payload[key] = value;
    }

    return payload;
}
