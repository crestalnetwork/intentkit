import { Sparkles } from "lucide-react";

interface ThinkingBlockProps {
  thinking: string;
}

export function ThinkingBlock({ thinking }: ThinkingBlockProps) {
  return (
    <details className="mb-2 rounded border border-border/50 bg-muted/30 text-muted-foreground text-xs">
      <summary className="flex cursor-pointer items-center gap-1.5 px-2 py-1.5 select-none">
        <Sparkles className="h-3 w-3" />
        <span>Thinking</span>
      </summary>
      <div className="px-2 pb-2 whitespace-pre-wrap">{thinking}</div>
    </details>
  );
}
