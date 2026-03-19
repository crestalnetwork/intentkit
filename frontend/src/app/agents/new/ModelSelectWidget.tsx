"use client";

import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { WidgetProps } from "@rjsf/utils";
import { useQuery } from "@tanstack/react-query";
import { metadataApi, LLMModelInfo } from "@/lib/api";

function formatLength(tokens: number): string {
  if (tokens >= 1_000_000) {
    const val = tokens / 1_000_000;
    return val % 1 === 0 ? `${val}M` : `${val.toFixed(1)}M`;
  }
  if (tokens >= 1_000) {
    const val = tokens / 1_000;
    return val % 1 === 0 ? `${val}K` : `${val.toFixed(1)}K`;
  }
  return String(tokens);
}

function RatingBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, (value / 5) * 100));
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-20 shrink-0">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs w-4 text-right">{value}</span>
    </div>
  );
}

function InfoPanel({ model }: { model: LLMModelInfo }) {
  return (
    <div className="space-y-3 p-3 text-sm">
      <div>
        <div className="font-semibold">{model.name}</div>
        <div className="text-xs text-muted-foreground">
          {model.provider_name}
        </div>
      </div>

      <div className="space-y-1.5">
        {model.price_level !== null && (
          <RatingBar label="Price Level" value={model.price_level} />
        )}
        <RatingBar label="Intelligence" value={model.intelligence} />
        <RatingBar label="Speed" value={model.speed} />
      </div>

      <div className="flex gap-4 text-xs">
        <div>
          <span className="text-muted-foreground">Context: </span>
          <span className="font-medium">
            {formatLength(model.context_length)}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground">Output: </span>
          <span className="font-medium">
            {formatLength(model.output_length)}
          </span>
        </div>
      </div>

      {model.supports_image_input && (
        <div className="flex gap-1.5 flex-wrap">
          <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium">
            Image
          </span>
        </div>
      )}
    </div>
  );
}

export const ModelSelectWidget = (props: WidgetProps) => {
  const {
    id,
    value,
    required,
    disabled,
    readonly,
    onChange,
    onBlur,
    onFocus,
    rawErrors = [],
  } = props;

  const [isOpen, setIsOpen] = useState(false);
  const [hoveredModel, setHoveredModel] = useState<LLMModelInfo | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const { data: models } = useQuery<LLMModelInfo[]>({
    queryKey: ["llm-models"],
    queryFn: () => metadataApi.getLLMs(),
    staleTime: 5 * 60 * 1000,
  });

  const enabledModels = useMemo(
    () => models?.filter((m) => m.enabled !== false) ?? [],
    [models],
  );

  const grouped = useMemo(() => {
    return enabledModels.reduce<Record<string, LLMModelInfo[]>>(
      (acc, model) => {
        const key = model.provider_name;
        if (!acc[key]) acc[key] = [];
        acc[key].push(model);
        return acc;
      },
      {},
    );
  }, [enabledModels]);

  const selectedModel = useMemo(
    () => enabledModels.find((m) => m.id === value) ?? null,
    [enabledModels, value],
  );

  // The model to show in the info panel: hovered takes priority over selected
  const displayModel = hoveredModel ?? selectedModel;

  // Close dropdown on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node) &&
        panelRef.current &&
        !panelRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
        setHoveredModel(null);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setHoveredModel(null);
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen]);

  // Compute panel position
  const [panelStyle, setPanelStyle] = useState<React.CSSProperties>({});
  const updatePanelPosition = useCallback(() => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const panelWidth = 280;
    const spaceRight = window.innerWidth - rect.right;
    if (spaceRight >= panelWidth + 8) {
      setPanelStyle({ top: rect.top, left: rect.right + 8, width: panelWidth });
    } else {
      setPanelStyle({
        top: rect.top,
        left: rect.left - panelWidth - 8,
        width: panelWidth,
      });
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    updatePanelPosition();
    window.addEventListener("scroll", updatePanelPosition, true);
    window.addEventListener("resize", updatePanelPosition);
    return () => {
      window.removeEventListener("scroll", updatePanelPosition, true);
      window.removeEventListener("resize", updatePanelPosition);
    };
  }, [isOpen, updatePanelPosition]);

  const handleSelect = (modelId: string) => {
    onChange(modelId || undefined);
    setIsOpen(false);
    setHoveredModel(null);
  };

  const isDisabled = disabled || readonly;

  return (
    <div className="mb-4 relative" ref={containerRef}>
      {/* Trigger button styled like a select */}
      <button
        type="button"
        id={id}
        className={`flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
          rawErrors.length > 0 ? "border-destructive" : ""
        }`}
        disabled={isDisabled}
        onClick={() => {
          if (!isDisabled) setIsOpen(!isOpen);
        }}
        onFocus={() => onFocus && onFocus(id, value)}
        onBlur={() => onBlur && onBlur(id, value)}
        aria-required={required}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span className={value ? "" : "text-muted-foreground"}>
          {selectedModel ? selectedModel.name : "Select..."}
        </span>
        <svg
          className={`h-4 w-4 opacity-50 transition-transform ${isOpen ? "rotate-180" : ""}`}
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {/* Dropdown list */}
      {isOpen && (
        <div
          ref={dropdownRef}
          className="absolute z-50 mt-1 w-full max-h-64 overflow-auto rounded-md border bg-popover text-popover-foreground shadow-md"
          role="listbox"
        >
          {Object.entries(grouped).map(([providerName, providerModels]) => (
            <div key={providerName}>
              <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground bg-muted/50 sticky top-0">
                {providerName}
              </div>
              {providerModels.map((model) => (
                <div
                  key={model.id}
                  role="option"
                  aria-selected={model.id === value}
                  className={`px-3 py-2 text-sm cursor-pointer ${
                    model.id === value
                      ? "bg-accent text-accent-foreground"
                      : "hover:bg-accent/50"
                  } ${
                    hoveredModel?.id === model.id && model.id !== value
                      ? "bg-accent/50"
                      : ""
                  }`}
                  onClick={() => handleSelect(model.id)}
                  onMouseEnter={() => setHoveredModel(model)}
                  onMouseLeave={() => setHoveredModel(null)}
                >
                  {model.name}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Floating info panel */}
      {isOpen && displayModel && (
        <div
          ref={panelRef}
          className="fixed z-50 rounded-md border bg-popover text-popover-foreground shadow-md"
          style={panelStyle}
        >
          <InfoPanel model={displayModel} />
        </div>
      )}
    </div>
  );
};
