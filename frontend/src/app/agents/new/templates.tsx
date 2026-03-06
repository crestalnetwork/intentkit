import React, { useState } from "react";
import { FieldTemplateProps, ObjectFieldTemplateProps } from "@rjsf/utils";
import { ChevronDown, ChevronRight } from "lucide-react";

export const FieldTemplate = (props: FieldTemplateProps) => {
    const {
        id,
        label,
        children,
        errors,
        help,
        description,
        hidden,
        required,
        displayLabel,
    } = props;

    if (hidden) {
        return <div className="hidden">{children}</div>;
    }

    return (
        <div className="mb-4">
            {displayLabel && label && (
                <label htmlFor={id} className="block text-base font-bold mb-1">
                    {label} {required ? "*" : null}
                </label>
            )}
            {displayLabel && description && (
                <div className="text-sm text-muted-foreground mb-1">
                    {description}
                </div>
            )}
            {children}
            {errors}
            {help}
        </div>
    );
};

export const ObjectFieldTemplate = (props: ObjectFieldTemplateProps) => {
    const [showAdvanced, setShowAdvanced] = useState(false);
    const { properties, schema } = props;

    const schemaProperties = (schema.properties || {}) as Record<string, Record<string, unknown>>;

    // Also check properties inside if/then for conditional advanced fields
    const thenProperties = ((schema as Record<string, unknown>).then as Record<string, unknown>)?.properties as Record<string, Record<string, unknown>> | undefined;

    const isAdvanced = (name: string): boolean => {
        if (schemaProperties[name]?.["x-advanced"]) return true;
        if (thenProperties?.[name]?.["x-advanced"]) return true;
        return false;
    };

    const normalFields = properties.filter(p => !isAdvanced(p.name));
    const advancedFields = properties.filter(p => isAdvanced(p.name));

    if (advancedFields.length === 0) {
        return <>{properties.map(p => p.content)}</>;
    }

    return (
        <>
            {normalFields.map(p => p.content)}
            <div className="border-t pt-2 mt-4">
                <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
                >
                    {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    Advanced Settings
                </button>
                {showAdvanced && (
                    <div className="pl-2">
                        {advancedFields.map(p => p.content)}
                    </div>
                )}
            </div>
        </>
    );
};

export const templates = {
    FieldTemplate,
    ObjectFieldTemplate,
};
