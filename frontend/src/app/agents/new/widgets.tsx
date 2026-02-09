import React from "react";
import { WidgetProps, BaseInputTemplateProps } from "@rjsf/utils";
import { Input } from "@/components/ui/input";
// Checking file list earlier, Label was not in components/ui. I will use a simple label implementation or standard label tag.

export const BaseInputTemplate = (props: BaseInputTemplateProps) => {
    const {
        id,
        placeholder,
        required,
        readonly,
        disabled,
        type,
        value,
        onChange,
        onBlur,
        onFocus,
        autofocus,
        options,
        rawErrors = [],
    } = props;
    const inputProps = {
        id,
        placeholder,
        required,
        disabled: disabled || readonly,
        type,
        value: value || "",
        onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
            onChange(e.target.value === "" ? options.emptyValue : e.target.value),
        onBlur: onBlur && ((e: React.FocusEvent<HTMLInputElement>) => onBlur(id, e.target.value)),
        onFocus: onFocus && ((e: React.FocusEvent<HTMLInputElement>) => onFocus(id, e.target.value)),
        autoFocus: autofocus,
    };

    return (
        <div className="mb-4">
            <Input {...inputProps} className={rawErrors.length > 0 ? "border-destructive" : ""} />
        </div>
    );
};

export const TextareaWidget = (props: WidgetProps) => {
    const {
        id,
        placeholder,
        value,
        required,
        disabled,
        readonly,
        autofocus,
        onChange,
        onBlur,
        onFocus,
        options,
        rawErrors = [],
    } = props;

    return (
        <div className="mb-4">
            <textarea
                id={id}
                className={`flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${rawErrors.length > 0 ? "border-destructive" : ""
                    }`}
                value={value || ""}
                placeholder={placeholder}
                required={required}
                disabled={disabled || readonly}
                autoFocus={autofocus}
                rows={options.rows || 5}
                onChange={(e) => onChange(e.target.value === "" ? options.emptyValue : e.target.value)}
                onBlur={onBlur && ((e) => onBlur(id, e.target.value))}
                onFocus={onFocus && ((e) => onFocus(id, e.target.value))}
            />
        </div>
    );
};

export const SelectWidget = (props: WidgetProps) => {
    const {
        id,
        options,
        value,
        required,
        disabled,
        readonly,
        multiple,
        autofocus,
        onChange,
        onBlur,
        onFocus,
        schema,
        rawErrors = [],
    } = props;
    const { enumOptions, enumDisabled } = options;

    return (
        <div className="mb-4">
            <select
                id={id}
                multiple={multiple}
                className={`flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${rawErrors.length > 0 ? "border-destructive" : ""
                    }`}
                value={value || ""}
                required={required}
                disabled={disabled || readonly}
                autoFocus={autofocus}
                onBlur={onBlur && ((e) => onBlur(id, e.target.value))}
                onFocus={onFocus && ((e) => onFocus(id, e.target.value))}
                onChange={(e) => onChange(e.target.value === "" ? options.emptyValue : e.target.value)}
            >
                {!multiple && schema.default === undefined && <option value="">Select...</option>}
                {(enumOptions as { value: string; label: string }[])?.map(({ value, label }, i) => {
                    const disabled = enumDisabled && (enumDisabled as string[]).indexOf(value) !== -1;
                    return (
                        <option key={i} value={value} disabled={disabled}>
                            {label}
                        </option>
                    );
                })}
            </select>
        </div>
    );
};

export const CheckboxWidget = (props: WidgetProps) => {
    const {
        id,
        value,
        disabled,
        readonly,
        onBlur,
        onFocus,
        onChange,
    } = props;

    return (
        <div className="mb-4">
            <input
                type="checkbox"
                id={id}
                checked={typeof value === "undefined" ? false : value}
                required={props.required}
                disabled={disabled || readonly}
                autoFocus={props.autofocus}
                onChange={(e) => onChange(e.target.checked)}
                onBlur={onBlur && ((e) => onBlur(id, e.target.checked))}
                onFocus={onFocus && ((e) => onFocus(id, e.target.checked))}
                className="h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
        </div>
    );
};

export const widgets = {
    BaseInputTemplate,
    TextareaWidget,
    SelectWidget,
    CheckboxWidget,
};
