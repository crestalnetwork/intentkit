import { Info } from "lucide-react";
import type { Agent } from "@/types/agent";

interface AgentInfoBarProps {
  agent: Agent;
}

export function AgentInfoBar({ agent }: AgentInfoBarProps) {
  return (
    <div className="mb-4 rounded-lg border bg-muted/50 p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="inline-flex items-center gap-1 rounded-md bg-background px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-gray-500/10">
          <Info className="h-3 w-3 text-muted-foreground" />
          {agent.model}
        </span>
        {agent.tools &&
          agent.tools.map((tool) => (
            <span
              key={tool}
              className="inline-flex items-center rounded-md bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-primary/20"
            >
              {tool}
            </span>
          ))}
        {agent.search_internet && (
          <span className="inline-flex items-center rounded-md bg-blue-500/10 text-blue-700 dark:text-blue-400 px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-blue-500/20">
            search
          </span>
        )}
      </div>
    </div>
  );
}
