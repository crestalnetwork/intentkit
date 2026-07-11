"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { MemorySections } from "@/components/features/MemorySections";
import { memoryApi } from "@/lib/api";
import { toast } from "@/hooks/use-toast";
import type { Memory } from "@/types/memory";

export default function ClientPage() {
  const queryClient = useQueryClient();

  const {
    data: memories = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["memories"],
    queryFn: () => memoryApi.list(),
    staleTime: 30_000,
  });

  const handleSave = async (memory: Memory, content: string) => {
    await memoryApi.update(memory.id, content);
    await queryClient.invalidateQueries({ queryKey: ["memories"] });
    toast({ title: "Memory updated", variant: "success" });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <div>
        <h1 className="text-2xl font-bold">Memory</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Agents manage these memories automatically as they work. You normally
          don&apos;t need to read or edit them — leave them alone unless you
          know exactly what you are doing.
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading memories...</p>
      ) : error ? (
        <p className="text-sm text-destructive">Failed to load memories.</p>
      ) : (
        <MemorySections memories={memories} onSave={handleSave} />
      )}
    </div>
  );
}
