import React from "react";
import { FieldTemplateProps } from "@rjsf/utils";

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
                <label htmlFor={id} className="block text-sm font-bold mb-1">
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

export const templates = {
    FieldTemplate,
};
