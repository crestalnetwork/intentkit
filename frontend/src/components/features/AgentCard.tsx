import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { AgentResponse } from "@/types/agent";
import { Bot, Cpu } from "lucide-react";
import Link from "next/link";

interface AgentCardProps {
    agent: AgentResponse;
}

export function AgentCard({ agent }: AgentCardProps) {
    const displayName = agent.name || agent.id;
    const displayDescription = agent.purpose || "No description available";

    // Extract active skills
    const activeSkills = agent.skills
        ? Object.entries(agent.skills)
            .filter(([, config]) => (config as { enabled: boolean }).enabled)
            .map(([category]) => category)
        : [];

    return (
        <Link href={`/agent?id=${agent.id}`} className="block h-full group">
            <Card className="flex flex-col h-full transition-colors hover:bg-muted/50 hover:border-primary/50">
                <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                        {agent.picture ? (
                            /* eslint-disable-next-line @next/next/no-img-element */
                            <img
                                src={agent.picture}
                                alt={displayName}
                                className="h-9 w-9 rounded-full object-cover"
                            />
                        ) : (
                            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10">
                                <Bot className="h-5 w-5 text-primary" />
                            </div>
                        )}
                        <div className="min-w-0 flex-1">
                            <CardTitle className="text-base font-semibold truncate leading-none">
                                {displayName}
                            </CardTitle>
                            <div className="flex items-center gap-2 mt-1.5 text-[10px] text-muted-foreground font-mono">
                                <span className="truncate max-w-[80px]" title={agent.id}>
                                    #{agent.id.slice(0, 8)}
                                </span>
                                <span className="w-px h-3 bg-border" />
                                <span className="flex items-center gap-1 truncate">
                                    <Cpu className="h-3 w-3" />
                                    {agent.model}
                                </span>
                            </div>
                        </div>
                    </div>
                    <CardDescription className="line-clamp-2 min-h-[2.5rem] mt-3 text-xs">
                        {displayDescription}
                    </CardDescription>
                </CardHeader>
                <CardContent className="flex-1 pt-0">
                    {activeSkills.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-auto">
                            {activeSkills.map((skill) => (
                                <span
                                    key={skill}
                                    className="inline-flex items-center rounded-md bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground ring-1 ring-inset ring-gray-500/10"
                                >
                                    {skill}
                                </span>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </Link>
    );
}
