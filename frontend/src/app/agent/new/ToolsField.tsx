"use client";
import { useQuery } from "@tanstack/react-query";
import { AdvancedSection } from "./AdvancedSection";
import { ToolsetCard } from "./ToolsetCard";
import { config } from "@/lib/config";
import { walletApi } from "@/lib/api";

interface ToolInfo {
    title?: string;
    description?: string;
}

interface ToolsetCatalogEntry {
    title?: string;
    description?: string;
    "x-icon"?: string;
    "x-web3"?: boolean;
    tools?: Record<string, ToolInfo>;
}

export type ToolCatalog = Record<string, ToolsetCatalogEntry>;

interface ToolsFieldProps {
    /** Flat list of enabled tool names -- the value stored on the agent. */
    value: string[] | undefined;
    onChange: (value: string[] | undefined) => void;
    /** Toolset catalog from GET /metadata/tools. */
    catalog: ToolCatalog;
}

/**
 * Tool picker for the agent form.
 *
 * The form value is a flat list of enabled tool names; the catalog of
 * categories and their tools comes from GET /metadata/tools.
 */
export function ToolsField({
    value,
    onChange,
    catalog,
}: ToolsFieldProps) {

    // Web3 toolsets are only selectable when the team owns at least one wallet.
    const { data: wallets } = useQuery({
        queryKey: ["wallets"],
        queryFn: () => walletApi.listWallets(),
    });
    const hasWallets = (wallets?.length ?? 0) > 0;

    const selected = new Set(value || []);

    const setSelected = (next: Set<string>) => {
        // Always an array, never undefined: the edit payload needs an explicit
        // empty list to clear the selection server-side.
        onChange(Array.from(next));
    };

    const handleToolToggle = (toolKey: string, enabled: boolean) => {
        const next = new Set(selected);
        if (enabled) {
            next.add(toolKey);
        } else {
            next.delete(toolKey);
        }
        setSelected(next);
    };

    // Sort by title; web3 toolsets go into a collapsible "Web3 Tools" group,
    // which is hidden entirely until the team owns a wallet
    const sortedCategories = Object.entries(catalog).sort(
        ([keyA, a], [keyB, b]) =>
            (a.title || keyA).localeCompare(b.title || keyB)
    );
    const regularCategories = sortedCategories.filter(
        ([, entry]) => entry["x-web3"] !== true
    );
    const web3Categories = sortedCategories.filter(
        ([, entry]) => entry["x-web3"] === true
    );
    const hasWeb3Selection = web3Categories.some(([, entry]) =>
        Object.keys(entry.tools || {}).some((toolKey) => selected.has(toolKey))
    );

    const renderCategory = ([categoryKey, categorySchema]: [
        string,
        ToolsetCatalogEntry,
    ]) => {
        const tools = Object.entries(categorySchema.tools || {}).map(
            ([toolKey, toolInfo]) => ({
                title: toolInfo.title || toolKey,
                description: toolInfo.description,
                enabled: selected.has(toolKey),
                onToggle: (enabled: boolean) =>
                    handleToolToggle(toolKey, enabled),
            })
        );

        // Build icon URL: relative paths get API base prefix, absolute URLs pass through
        const rawIcon = categorySchema["x-icon"];
        const iconUrl = rawIcon
            ? rawIcon.startsWith("/")
                ? `${config.apiBaseUrl}${rawIcon}`
                : rawIcon
            : undefined;

        return (
            <ToolsetCard
                key={categoryKey}
                title={categorySchema.title || categoryKey}
                description={categorySchema.description}
                iconUrl={iconUrl}
                tools={tools}
            />
        );
    };

    return (
        <div id="tools-field" className="space-y-4">
            {regularCategories.map(renderCategory)}
            {hasWallets && web3Categories.length > 0 && (
                <AdvancedSection
                    title="Web3 Tools"
                    defaultOpen={hasWeb3Selection}
                    bodyClassName="space-y-4"
                >
                    {web3Categories.map(renderCategory)}
                </AdvancedSection>
            )}
        </div>
    );
}
