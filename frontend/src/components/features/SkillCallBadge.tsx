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
import type { ChatMessageSkillCall } from "@/types/chat";

interface SkillCallBadgeProps {
  skillCall: ChatMessageSkillCall;
  isLoading?: boolean;
}

export function SkillCallBadge({ skillCall, isLoading }: SkillCallBadgeProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Extract skill display name (remove prefix like "twitter_", "web_", etc.)
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

  // Get skill category (prefix)
  const getCategory = (name: string) => {
    const parts = name.split("_");
    if (parts.length > 1) {
      return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
    }
    return "Skill";
  };

  const displayName = getDisplayName(skillCall.name);
  const category = getCategory(skillCall.name);

  return (
    <div className="inline-block">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all",
          "border cursor-pointer hover:shadow-sm",
          isLoading
            ? "bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-300"
            : skillCall.success
              ? "bg-green-50 border-green-200 text-green-700 dark:bg-green-950 dark:border-green-800 dark:text-green-300"
              : "bg-red-50 border-red-200 text-red-700 dark:bg-red-950 dark:border-red-800 dark:text-red-300",
        )}
      >
        {isLoading ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : skillCall.success ? (
          <CheckCircle className="h-3 w-3" />
        ) : (
          <XCircle className="h-3 w-3" />
        )}
        <Wrench className="h-3 w-3 opacity-60" />
        <span className="opacity-60">{category}:</span>
        <span>{displayName}</span>
        {isExpanded ? (
          <ChevronUp className="h-3 w-3 ml-0.5" />
        ) : (
          <ChevronDown className="h-3 w-3 ml-0.5" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-2 p-3 rounded-lg bg-muted/50 border text-xs space-y-2 max-w-md">
          {/* Parameters */}
          {skillCall.parameters &&
            Object.keys(skillCall.parameters).length > 0 && (
              <div>
                <div className="font-medium text-muted-foreground mb-1">
                  Parameters:
                </div>
                <pre className="bg-background p-2 rounded overflow-x-auto text-[10px] leading-relaxed">
                  {JSON.stringify(skillCall.parameters, null, 2)}
                </pre>
              </div>
            )}

          {/* Response (if success) */}
          {skillCall.success && skillCall.response && (
            <div>
              <div className="font-medium text-muted-foreground mb-1">
                Response:
              </div>
              <pre className="bg-background p-2 rounded overflow-x-auto text-[10px] leading-relaxed max-h-40 overflow-y-auto">
                {skillCall.response.length > 500
                  ? `${skillCall.response.substring(0, 500)}...`
                  : skillCall.response}
              </pre>
            </div>
          )}

          {/* Error (if failed) */}
          {!skillCall.success && skillCall.error_message && (
            <div>
              <div className="font-medium text-red-600 dark:text-red-400 mb-1">
                Error:
              </div>
              <pre className="bg-red-50 dark:bg-red-950/50 p-2 rounded overflow-x-auto text-[10px] leading-relaxed text-red-700 dark:text-red-300">
                {skillCall.error_message}
              </pre>
            </div>
          )}

          {/* Credit cost if available */}
          {skillCall.credit_cost !== undefined && skillCall.credit_cost > 0 && (
            <div className="text-muted-foreground">
              Credit cost: {skillCall.credit_cost}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface SkillCallBadgeListProps {
  skillCalls: ChatMessageSkillCall[];
  isLoading?: boolean;
}

export function SkillCallBadgeList({
  skillCalls,
  isLoading,
}: SkillCallBadgeListProps) {
  if (!skillCalls || skillCalls.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {skillCalls.map((skillCall, index) => (
        <SkillCallBadge
          key={skillCall.id || `skill-${index}`}
          skillCall={skillCall}
          isLoading={isLoading && index === skillCalls.length - 1}
        />
      ))}
    </div>
  );
}
