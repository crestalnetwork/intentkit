"use client";

import { config } from "@/lib/config";

export function FloatingFooter() {
  return (
    <div className="fixed bottom-0 left-0 z-50 px-3 py-1 text-[10px] text-muted-foreground/50">
      IntentKit {config.version} &copy; {new Date().getFullYear()} Crestal
    </div>
  );
}
