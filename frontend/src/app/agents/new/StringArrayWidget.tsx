import React, { useState, useRef, useCallback } from "react";
import { WidgetProps } from "@rjsf/utils";
import { X } from "lucide-react";

/**
 * A widget for editing string arrays as tags.
 * Users can type a value and press Enter or comma to add it.
 * Each item is displayed as a removable tag.
 */
export const StringArrayWidget = (props: WidgetProps) => {
    const {
        id,
        value,
        disabled,
        readonly,
        placeholder,
        onChange,
        rawErrors = [],
    } = props;

    const items: string[] = Array.isArray(value) ? value : [];
    const [inputValue, setInputValue] = useState("");
    const inputRef = useRef<HTMLInputElement>(null);

    const addItem = useCallback(
        (raw: string) => {
            const trimmed = raw.trim();
            if (trimmed && !items.includes(trimmed)) {
                onChange([...items, trimmed]);
            }
        },
        [items, onChange],
    );

    const removeItem = useCallback(
        (index: number) => {
            const next = items.filter((_, i) => i !== index);
            onChange(next.length > 0 ? next : undefined);
        },
        [items, onChange],
    );

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            addItem(inputValue);
            setInputValue("");
        } else if (e.key === "Backspace" && inputValue === "" && items.length > 0) {
            removeItem(items.length - 1);
        }
    };

    const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
        const pasted = e.clipboardData.getData("text");
        if (pasted.includes(",")) {
            e.preventDefault();
            const parts = pasted.split(",").map((s) => s.trim()).filter(Boolean);
            const unique = [...new Set([...items, ...parts])];
            onChange(unique);
            setInputValue("");
        }
    };

    const handleBlur = () => {
        if (inputValue.trim()) {
            addItem(inputValue);
            setInputValue("");
        }
    };

    return (
        <div className="mb-4">
            <div
                className={`flex flex-wrap items-center gap-1.5 min-h-[40px] w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${
                    rawErrors.length > 0 ? "border-destructive" : "border-input"
                } ${disabled || readonly ? "opacity-50 cursor-not-allowed" : "cursor-text"}`}
                onClick={() => inputRef.current?.focus()}
            >
                {items.map((item, index) => (
                    <span
                        key={index}
                        className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-sm text-secondary-foreground"
                    >
                        {item}
                        {!disabled && !readonly && (
                            <button
                                type="button"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    removeItem(index);
                                }}
                                className="text-muted-foreground hover:text-foreground"
                            >
                                <X className="h-3 w-3" />
                            </button>
                        )}
                    </span>
                ))}
                <input
                    ref={inputRef}
                    id={id}
                    type="text"
                    value={inputValue}
                    disabled={disabled || readonly}
                    placeholder={items.length === 0 ? (placeholder || "Type and press Enter to add") : ""}
                    className="flex-1 min-w-[120px] bg-transparent outline-none placeholder:text-muted-foreground"
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onPaste={handlePaste}
                    onBlur={handleBlur}
                />
            </div>
        </div>
    );
};
