"use client";

import React from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

/**
 * Form field primitives for the agent form.
 *
 * The agent form used to be generated from the backend's JSON schema via RJSF.
 * It is now hardcoded, so labels, help text and constraints live in
 * `AgentForm.tsx` next to the field they describe. These primitives only carry
 * the shared layout, which matches what the old RJSF FieldTemplate produced.
 */

interface FieldShellProps {
    id: string;
    label: string;
    description?: string;
    required?: boolean;
    error?: string;
    children: React.ReactNode;
}

export function FieldShell({
    id,
    label,
    description,
    required,
    error,
    children,
}: FieldShellProps) {
    return (
        <div className="mb-4">
            <label htmlFor={id} className="block text-base font-bold mb-1">
                {label} {required ? "*" : null}
            </label>
            {description && (
                <div className="text-sm text-muted-foreground mb-1">{description}</div>
            )}
            {children}
            {error && <p className="mt-1 text-sm text-destructive">{error}</p>}
        </div>
    );
}

interface TextFieldProps {
    id: string;
    label: string;
    description?: string;
    placeholder?: string;
    value: string;
    onChange: (value: string) => void;
    required?: boolean;
    disabled?: boolean;
    maxLength?: number;
    error?: string;
}

export function TextField({
    id,
    label,
    description,
    placeholder,
    value,
    onChange,
    required,
    disabled,
    maxLength,
    error,
}: TextFieldProps) {
    return (
        <FieldShell
            id={id}
            label={label}
            description={description}
            required={required}
            error={error}
        >
            <Input
                id={id}
                value={value}
                placeholder={placeholder}
                disabled={disabled}
                maxLength={maxLength}
                onChange={(e) => onChange(e.target.value)}
                className={error ? "border-destructive" : ""}
            />
        </FieldShell>
    );
}

interface TextAreaFieldProps extends Omit<TextFieldProps, "maxLength"> {
    rows?: number;
    maxLength?: number;
}

export function TextAreaField({
    id,
    label,
    description,
    placeholder,
    value,
    onChange,
    required,
    disabled,
    rows = 6,
    maxLength,
    error,
}: TextAreaFieldProps) {
    return (
        <FieldShell
            id={id}
            label={label}
            description={description}
            required={required}
            error={error}
        >
            <Textarea
                id={id}
                value={value}
                placeholder={placeholder}
                disabled={disabled}
                rows={rows}
                maxLength={maxLength}
                onChange={(e) => onChange(e.target.value)}
                className={error ? "border-destructive" : ""}
            />
        </FieldShell>
    );
}

interface CheckboxFieldProps {
    id: string;
    label: string;
    description?: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
    disabled?: boolean;
}

export function CheckboxField({
    id,
    label,
    description,
    checked,
    onChange,
    disabled,
}: CheckboxFieldProps) {
    return (
        <div className="mb-4">
            <label htmlFor={id} className="block text-base font-bold mb-1">
                {label}
            </label>
            <div className="flex items-start gap-2">
                <input
                    type="checkbox"
                    id={id}
                    checked={checked}
                    disabled={disabled}
                    onChange={(e) => onChange(e.target.checked)}
                    className="mt-1 h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                />
                {description && (
                    <p className="text-sm text-muted-foreground">{description}</p>
                )}
            </div>
        </div>
    );
}

interface SelectFieldProps {
    id: string;
    label: string;
    description?: string;
    value: string;
    onChange: (value: string) => void;
    options: { value: string; label: string }[];
    placeholder?: string;
    disabled?: boolean;
    error?: string;
}

export function SelectField({
    id,
    label,
    description,
    value,
    onChange,
    options,
    placeholder = "Select...",
    disabled,
    error,
}: SelectFieldProps) {
    return (
        <FieldShell id={id} label={label} description={description} error={error}>
            <select
                id={id}
                value={value}
                disabled={disabled}
                onChange={(e) => onChange(e.target.value)}
                className={`flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
                    error ? "border-destructive" : ""
                }`}
            >
                <option value="">{placeholder}</option>
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
        </FieldShell>
    );
}

interface SectionProps {
    title: string;
    children: React.ReactNode;
}

export function Section({ title, children }: SectionProps) {
    return (
        <section className="mb-8">
            <h2 className="mb-4 border-b pb-2 text-lg font-semibold">{title}</h2>
            {children}
        </section>
    );
}
