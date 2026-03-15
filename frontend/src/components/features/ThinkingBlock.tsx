"use client";

import { useState } from "react";
import { Sparkles, ChevronDown, ChevronUp } from "lucide-react";

interface ThinkingBlockProps {
  thinking: string;
}

export function ThinkingBlock({ thinking }: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all border cursor-pointer hover:shadow-sm bg-muted/30 border-border/50 text-muted-foreground"
      >
        <Sparkles className="h-3 w-3" />
        <span>Thinking</span>
        {isExpanded ? (
          <ChevronUp className="h-3 w-3 ml-0.5" />
        ) : (
          <ChevronDown className="h-3 w-3 ml-0.5" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-1 p-2 rounded border border-border/50 bg-muted/30 text-muted-foreground text-xs whitespace-pre-wrap">
          {thinking}
        </div>
      )}
    </div>
  );
}
