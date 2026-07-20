import { customizeValidator } from "@rjsf/validator-ajv8";
import { RegistryFieldsType } from "@rjsf/utils";
import { ToolsField } from "./ToolsField";

// Cache lifetime for the shared agent-schema query
export const SCHEMA_STALE_TIME = 5 * 60 * 1000;

// Shared RJSF validator
export const validator = customizeValidator({
    ajvOptionsOverrides: {
        removeAdditional: true,
    },
});

// Shared RJSF custom fields
export const fields: RegistryFieldsType = {
    ToolsField: ToolsField,
};

// Stable error logger for RJSF onError
export const onFormError = console.log.bind(console, "errors");

/**
 * Generate uiSchema from a JSON schema with custom x-* directives.
 * @param schema - The agent JSON schema
 * @param readOnlyFields - Field names to mark as read-only (e.g. ["id"] in edit mode)
 */
export function generateUiSchema(
    schema: Record<string, unknown> | undefined,
    readOnlyFields?: string[],
) {
    const uiSchema: Record<string, unknown> = {
        "ui:title": " ",
        "ui:description": " ",
    };

    if (schema && typeof schema.properties === "object" && schema.properties !== null) {
        const properties = schema.properties as Record<string, Record<string, unknown>>;
        const readOnlySet = new Set(readOnlyFields ?? []);

        Object.keys(properties).forEach((key) => {
            const property = properties[key];
            const uiProperty: Record<string, unknown> = {};

            if (key === "tools") {
                uiProperty["ui:field"] = "ToolsField";
            }

            if (readOnlySet.has(key)) {
                uiProperty["ui:readonly"] = true;
            }

            if (property["x-component"] === "category-select") {
                uiProperty["ui:widget"] = "ModelSelectWidget";
            }

            if (property["x-component"] === "picture-upload") {
                uiProperty["ui:widget"] = "PictureWidget";
            }

            if (typeof property["x-placeholder"] === "string") {
                uiProperty["ui:placeholder"] = property["x-placeholder"];
            }

            if (typeof property.maxLength === "number" && property.maxLength > 200) {
                uiProperty["ui:widget"] = "textarea";
            }

            if (
                key !== "tools" &&
                property.type === "array" &&
                (property.items as Record<string, unknown>)?.type === "string"
            ) {
                uiProperty["ui:widget"] = "StringArrayWidget";
            }

            if (Object.keys(uiProperty).length > 0) {
                uiSchema[key] = uiProperty;
            }
        });
    }

    return uiSchema;
}

/**
 * Filter validation errors: remove type errors for optional empty fields.
 */
export function createTransformErrors(
    formData: Record<string, unknown>,
    schema: Record<string, unknown> | undefined,
) {
    const requiredFields = (schema?.required as string[]) || [];

    return (errors: ReturnType<typeof validator.validateFormData>["errors"]) => {
        return errors.filter((error) => {
            const fieldName = error.property?.replace(/^\./, "").split(".")[0] || "";

            if (requiredFields.includes(fieldName)) {
                return true;
            }

            if (error.name === "type" || error.name === "enum") {
                const fieldValue = formData[fieldName];
                if (fieldValue === undefined || fieldValue === null || fieldValue === "") {
                    return false;
                }
            }

            return true;
        });
    };
}

/**
 * Clean up the tools name list before submission.
 * - Deduplicates names
 * - Optionally filters out names not in the schema catalog (for edit mode)
 */
export function cleanToolsData(
    data: Record<string, unknown>,
    schema?: Record<string, unknown>,
): Record<string, unknown> {
    const tools = data.tools as string[] | undefined;
    const restData = { ...data };
    delete (restData as Record<string, unknown>).autonomous;
    if (!tools) return restData;

    const validTools = getValidToolNames(schema);
    const cleaned = Array.from(new Set(tools)).filter(
        (name) => !validTools || validTools.has(name),
    );

    return {
        ...restData,
        tools: cleaned.length > 0 ? cleaned : undefined,
    };
}

/**
 * Filter agent data to only include fields defined in the schema.
 * Accepts any object (e.g. a typed AgentResponse) so callers need no cast.
 */
export function filterBySchema(
    agent: object,
    schemaData: Record<string, unknown>,
): Record<string, unknown> {
    const agentData = agent as Record<string, unknown>;
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
}

// --- Internal helpers ---

function getValidToolNames(schema?: Record<string, unknown>): Set<string> | null {
    if (!schema?.properties) return null;
    const schemaProperties = schema.properties as Record<string, Record<string, unknown>>;
    const toolsSchema = schemaProperties.tools;
    const catalog = toolsSchema?.["x-catalog"] as
        | Record<string, { tools?: Record<string, unknown> }>
        | undefined;
    if (!catalog) return null;
    const names = new Set<string>();
    for (const entry of Object.values(catalog)) {
        for (const name of Object.keys(entry.tools || {})) {
            names.add(name);
        }
    }
    return names;
}
