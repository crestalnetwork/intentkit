"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  FileText,
  Loader2,
  Mail,
  Plug,
  Trash2,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { linkApi, type LinkAppInfo, type TeamLink } from "@/lib/api";
import { toast } from "@/hooks/use-toast";

const APP_ICONS: Record<string, LucideIcon> = {
  twitter: AtSign,
  notion: FileText,
  gmail: Mail,
};

function LinkRow({
  link,
  onUnlink,
  isUnlinking,
}: {
  link: TeamLink;
  onUnlink: (linkId: string) => void;
  isUnlinking: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2 text-sm">
      <div className="flex items-center gap-2 min-w-0">
        <span className="truncate">
          {link.account_label || link.connected_account_id}
        </span>
        {link.status !== "active" && (
          <Badge variant="destructive" className="capitalize">
            {link.status}
          </Badge>
        )}
      </div>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
            disabled={isUnlinking}
          >
            {isUnlinking ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            <span className="sr-only">Unlink</span>
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unlink this account?</AlertDialogTitle>
            <AlertDialogDescription>
              The lead agent will lose access to{" "}
              {link.account_label || "this account"} immediately. You can link
              it again at any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => onUnlink(link.id)}>
              Unlink
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function AppCard({ info, enabled }: { info: LinkAppInfo; enabled: boolean }) {
  const queryClient = useQueryClient();
  const Icon = APP_ICONS[info.app] ?? Plug;
  const activeCount = info.links.filter((l) => l.status === "active").length;

  const connect = useMutation({
    mutationFn: () => linkApi.connectLink(info.app),
    onSuccess: ({ url }) => {
      if (!url) {
        toast({
          title: "Could not start linking",
          description: "The server returned no auth URL. Please try again.",
          variant: "destructive",
        });
        return;
      }
      // Full-page redirect to Composio's hosted auth flow; it returns to
      // /oauth/callback when done.
      window.location.href = url;
    },
    onError: (err) => {
      toast({
        title: "Could not start linking",
        description: err instanceof Error ? err.message : "Please try again.",
        variant: "destructive",
      });
    },
  });

  const unlink = useMutation({
    mutationFn: (linkId: string) => linkApi.deleteLink(linkId),
    onSuccess: () => {
      toast({ title: "Account unlinked", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["links"] });
    },
    onError: (err) => {
      toast({
        title: "Error",
        description: err instanceof Error ? err.message : "Failed to unlink",
        variant: "destructive",
      });
    },
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {info.name}
        </CardTitle>
        <Badge variant={activeCount > 0 ? "default" : "secondary"}>
          {activeCount > 0 ? `${activeCount} linked` : "Not linked"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{info.description}</p>

        {info.links.length > 0 && (
          <div className="rounded-md border divide-y">
            {info.links.map((link) => (
              <LinkRow
                key={link.id}
                link={link}
                onUnlink={(id) => unlink.mutate(id)}
                isUnlinking={unlink.isPending && unlink.variables === link.id}
              />
            ))}
          </div>
        )}

        <Button
          size="sm"
          variant={info.links.length > 0 ? "outline" : "default"}
          onClick={() => connect.mutate()}
          // isSuccess keeps the button disabled while the full-page redirect
          // unloads, so a double click can't fire a second link attempt.
          disabled={!enabled || connect.isPending || connect.isSuccess}
        >
          {connect.isPending || connect.isSuccess ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Plug className="mr-2 h-4 w-4" />
          )}
          {info.links.length > 0 ? "Link another account" : "Link account"}
        </Button>
      </CardContent>
    </Card>
  );
}

export default function LinksPage() {
  // listLinks triggers a server-side Composio status sync, so don't refire
  // it on every window focus.
  const { data, isLoading, isError } = useQuery({
    queryKey: ["links"],
    queryFn: () => linkApi.listLinks(),
    staleTime: 30_000,
  });

  return (
    <div className="container py-10 max-w-2xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Links</h1>
        <p className="text-muted-foreground mt-2">
          Link external app accounts so the lead agent can act through them.
        </p>
      </div>

      {isError ? (
        <Card>
          <CardContent className="py-4 text-sm text-muted-foreground">
            Failed to load links. Please refresh the page to try again.
          </CardContent>
        </Card>
      ) : isLoading || !data ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          {!data.enabled && (
            <Card>
              <CardContent className="py-4 text-sm text-muted-foreground">
                Links are not available on this deployment (COMPOSIO_API_KEY
                is not configured).
              </CardContent>
            </Card>
          )}
          <div className="space-y-4">
            {data.apps.map((info) => (
              <AppCard key={info.app} info={info} enabled={data.enabled} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
