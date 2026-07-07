"use client";

import { useState } from "react";
import {
  CheckCircle,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatMessageToolCall } from "@/types/chat";

interface ToolCallBadgeProps {
  toolCall: ChatMessageToolCall;
}

export function ToolCallBadge({ toolCall }: ToolCallBadgeProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  // A call without a result yet (pending frame) is still running.
  const isLoading = toolCall.success === undefined;

  // Extract tool display name (remove prefix like "twitter_", "web_", etc.)
  const getDisplayName = (name: string) => {
    const parts = name.split("_");
    if (parts.length > 1) {
      // Capitalize first letter of each word after the prefix
      return parts
        .slice(1)
        .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
        .join(" ");
    }
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  // Get toolset (prefix)
  const getToolset = (name: string) => {
    const parts = name.split("_");
    if (parts.length > 1) {
      return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
    }
    return "Tool";
  };

  const displayName = getDisplayName(toolCall.name);
  const toolset = getToolset(toolCall.name);
  const displayMessage = toolCall.display_message?.trim();

  return (
    <div className="inline-block">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all",
          "border cursor-pointer hover:shadow-xs",
          isLoading
            ? "bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-300"
            : toolCall.success
              ? "bg-green-50 border-green-200 text-green-700 dark:bg-green-950 dark:border-green-800 dark:text-green-300"
              : "bg-red-50 border-red-200 text-red-700 dark:bg-red-950 dark:border-red-800 dark:text-red-300",
        )}
      >
        {isLoading ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : toolCall.success ? (
          <CheckCircle className="h-3 w-3" />
        ) : (
          <XCircle className="h-3 w-3" />
        )}
        <Wrench className="h-3 w-3 opacity-60" />
        {displayMessage ? (
          <span>{displayMessage}</span>
        ) : (
          <>
            <span className="opacity-60">{toolset}:</span>
            <span>{displayName}</span>
          </>
        )}
        {isExpanded ? (
          <ChevronUp className="h-3 w-3 ml-0.5" />
        ) : (
          <ChevronDown className="h-3 w-3 ml-0.5" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-2 p-3 rounded-lg bg-muted/50 border text-xs space-y-2 max-w-md">
          {/* Tool name (badge shows the display message instead) */}
          {displayMessage && (
            <div>
              <span className="font-medium text-muted-foreground">Tool: </span>
              <span>
                {toolset}: {displayName}
              </span>
            </div>
          )}

          {/* Parameters */}
          {toolCall.parameters &&
            Object.keys(toolCall.parameters).length > 0 && (
              <div>
                <div className="font-medium text-muted-foreground mb-1">
                  Request Parameters:
                </div>
                <pre className="bg-background p-2 rounded overflow-x-auto text-[10px] leading-relaxed">
                  {JSON.stringify(toolCall.parameters, null, 2)}
                </pre>
              </div>
            )}

          {/* Response (if success) */}
          {toolCall.success && toolCall.response && (
            <div>
              <div className="font-medium text-muted-foreground mb-1">
                Raw Response:
              </div>
              <pre className="bg-background p-2 rounded overflow-x-auto text-[10px] leading-relaxed max-h-96 overflow-y-auto whitespace-pre-wrap">
                {toolCall.response}
              </pre>
            </div>
          )}

          {/* Error (if failed) */}
          {!toolCall.success && toolCall.error_message && (
            <div>
              <div className="font-medium text-red-600 dark:text-red-400 mb-1">
                Error:
              </div>
              <pre className="bg-red-50 dark:bg-red-950/50 p-2 rounded overflow-x-auto text-[10px] leading-relaxed text-red-700 dark:text-red-300">
                {toolCall.error_message}
              </pre>
            </div>
          )}


        </div>
      )}
    </div>
  );
}

interface ToolCallBadgeListProps {
  toolCalls: ChatMessageToolCall[];
}

export function ToolCallBadgeList({ toolCalls }: ToolCallBadgeListProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {toolCalls.map((toolCall, index) => (
        <ToolCallBadge
          key={toolCall.id || `tool-${index}`}
          toolCall={toolCall}
        />
      ))}
    </div>
  );
}
