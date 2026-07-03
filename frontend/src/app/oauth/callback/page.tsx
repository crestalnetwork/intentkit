"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Check, X } from "lucide-react";
import { linkApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Status = "working" | "ok" | "error";

/**
 * OAuth landing page for Composio account links (the Links page).
 *
 * Composio redirects the browser here with ?connected_account_id&status after
 * the provider auth flow. We relay the id to the completion endpoint, which
 * verifies the account status against Composio directly — nothing from the
 * query string is trusted.
 */
function OAuthCallbackInner() {
  const params = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<Status>("working");
  const [message, setMessage] = useState("Finishing connection…");
  // Guard against React StrictMode double-invoking the effect (which would
  // fire the one-time completion twice).
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    let redirectTimer: ReturnType<typeof setTimeout> | undefined;

    void (async () => {
      const connectedAccountId = params.get("connected_account_id");
      if (!connectedAccountId) {
        setStatus("error");
        setMessage(
          params.get("status") || params.get("error")
            ? "Linking failed or was cancelled. Please try again."
            : "Missing OAuth parameters. Please start linking again.",
        );
        return;
      }

      try {
        await linkApi.completeLink(connectedAccountId);
        setStatus("ok");
        setMessage("Account linked! Redirecting…");
        redirectTimer = setTimeout(() => router.replace("/links"), 1200);
      } catch (e: unknown) {
        setStatus("error");
        setMessage(e instanceof Error ? e.message : "Linking failed.");
      }
    })();

    return () => clearTimeout(redirectTimer);
  }, [params, router]);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-4 text-center">
        {status === "working" && (
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        )}
        {status === "ok" && <Check className="h-8 w-8 text-green-500" />}
        {status === "error" && <X className="h-8 w-8 text-destructive" />}
        <p className="text-sm text-muted-foreground">{message}</p>
        {status === "error" && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.replace("/links")}
          >
            Back to Links
          </Button>
        )}
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <OAuthCallbackInner />
    </Suspense>
  );
}
