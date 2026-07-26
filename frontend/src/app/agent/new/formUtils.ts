import type { AgentFormValues } from "./AgentForm";

/**
 * Normalise form state into an API payload.
 *
 * `undefined` means "the form never set this" and is always dropped. `null`
 * means "the user explicitly cleared it" and is sent, because PATCH applies
 * `model_dump(exclude_unset=True)` server-side: an omitted key means "leave
 * alone", so a clear has to be transmitted or it silently does nothing.
 *
 * The two modes differ in how they treat emptiness:
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
        if (value === undefined) continue;

        if (value === null) {
            // An explicit clear. On create there is nothing to clear yet, and
            // the server's default should win.
            if (mode === "edit") payload[key] = null;
            continue;
        }

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

    // `model` is required by the API. An empty string is not a missing key: the
    // server's before-validator turns it into pick_default_model(), which is
    // what the old schema-driven form got from the injected schema default.
    // Without this, creating an agent without opening the model picker 422s.
    if (mode === "create" && payload.model === undefined) {
        payload.model = "";
    }

    return payload;
}
