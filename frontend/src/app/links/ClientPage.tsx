"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  Briefcase,
  Calendar,
  CreditCard,
  Database,
  FileText,
  GitBranch,
  HardDrive,
  Inbox,
  ListTodo,
  Loader2,
  Mail,
  NotebookPen,
  Plug,
  Presentation,
  Search,
  Sheet,
  SquareKanban,
  Table,
  Trash2,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
  gmail: Mail,
  outlook: Inbox,
  googlecalendar: Calendar,
  linkedin: Briefcase,
  twitter: AtSign,
  supabase: Database,
  notion: NotebookPen,
  airtable: Table,
  googledocs: FileText,
  googlesheets: Sheet,
  googleslides: Presentation,
  googledrive: HardDrive,
  linear: ListTodo,
  github: GitBranch,
  jira: SquareKanban,
  stripe: CreditCard,
};

function LinkRow({
  link,
  onUnlink,
  isUnlinking,
  disabled,
}: {
  link: TeamLink;
  onUnlink: (linkId: string) => void;
  isUnlinking: boolean;
  disabled: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-1.5 text-sm">
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
            disabled={disabled}
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
    mutationFn: async () => {
      const res = await linkApi.connectLink(info.app);
      // An empty URL is a failure: reaching onSuccess would wedge the
      // button disabled (isSuccess) with nowhere to redirect to.
      if (!res.url)
        throw new Error("The server returned no auth URL. Please try again.");
      return res;
    },
    onSuccess: ({ url }) => {
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
      <CardHeader className="flex flex-row items-center justify-between space-y-0 gap-2 px-4 py-3">
        <CardTitle className="flex min-w-0 items-center gap-2 text-sm font-medium">
          <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="truncate">{info.name}</span>
          {activeCount > 0 && (
            <Badge variant="default" className="shrink-0 px-1.5">
              {activeCount}
            </Badge>
          )}
        </CardTitle>
        <Button
          size="sm"
          variant={activeCount > 0 ? "outline" : "default"}
          className="h-7 shrink-0 px-2.5 text-xs"
          onClick={() => connect.mutate()}
          // isSuccess keeps the button disabled while the full-page redirect
          // unloads, so a double click can't fire a second link attempt.
          disabled={!enabled || connect.isPending || connect.isSuccess}
        >
          {connect.isPending || connect.isSuccess ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plug className="mr-1 h-3.5 w-3.5" />
          )}
          {activeCount > 0 ? "Add" : "Link"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-2 px-4 pb-3 pt-0">
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {info.description}
        </p>

        {info.links.length > 0 && (
          <div className="rounded-md border divide-y">
            {info.links.map((link) => (
              <LinkRow
                key={link.id}
                link={link}
                onUnlink={(id) => unlink.mutate(id)}
                isUnlinking={unlink.isPending && unlink.variables === link.id}
                // One unlink at a time per card, so concurrent clicks can't
                // clobber each other's in-flight state.
                disabled={unlink.isPending}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AppSection({
  title,
  hint,
  apps,
  enabled,
}: {
  title: string;
  hint: string;
  apps: LinkAppInfo[];
  enabled: boolean;
}) {
  if (apps.length === 0) return null;
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{hint}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {apps.map((info) => (
          <AppCard key={info.app} info={info} enabled={enabled} />
        ))}
      </div>
    </section>
  );
}

export default function LinksPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);

  // listLinks triggers a server-side Composio status sync, so don't refire
  // it on every window focus.
  const { data, isLoading, isError } = useQuery({
    queryKey: ["links"],
    queryFn: () => linkApi.listLinks(),
    staleTime: 30_000,
  });

  const { userApps, teamApps } = useMemo(() => {
    const q = search.trim().toLowerCase();
    const visible = (data?.apps ?? []).filter(
      (info) =>
        (!category || info.categories.includes(category)) &&
        (!q ||
          info.name.toLowerCase().includes(q) ||
          info.description.toLowerCase().includes(q) ||
          info.categories.some((c) => c.toLowerCase().includes(q))),
    );
    return {
      userApps: visible.filter((a) => a.level === "user"),
      teamApps: visible.filter((a) => a.level !== "user"),
    };
  }, [data, search, category]);

  return (
    <div className="container py-10 max-w-5xl space-y-6">
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

          <div className="flex flex-col gap-3">
            <div className="relative sm:max-w-xs">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search apps..."
                aria-label="Search apps"
                className="h-9 pl-8"
              />
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Button
                variant={category === null ? "secondary" : "ghost"}
                size="sm"
                className="h-7 rounded-full px-3 text-xs"
                aria-pressed={category === null}
                onClick={() => setCategory(null)}
              >
                All
              </Button>
              {data.categories.map((c) => (
                <Button
                  key={c}
                  variant={category === c ? "secondary" : "ghost"}
                  size="sm"
                  className="h-7 rounded-full px-3 text-xs"
                  aria-pressed={category === c}
                  onClick={() => setCategory(category === c ? null : c)}
                >
                  {c}
                </Button>
              ))}
            </div>
          </div>

          {userApps.length === 0 && teamApps.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No apps match your search.
            </p>
          ) : (
            <div className="space-y-8">
              <AppSection
                title="Personal apps"
                hint="Each user links their own accounts; the agent uses yours when talking to you."
                apps={userApps}
                enabled={data.enabled}
              />
              <AppSection
                title="Team apps"
                hint="Shared accounts, used in every conversation."
                apps={teamApps}
                enabled={data.enabled}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
