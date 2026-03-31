"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, Trash2, Loader2, Check, Radio, Copy, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChatSidebar } from "@/components/features/ChatSidebar";
import { leadApi } from "@/lib/api";
import {
  channelApi,
  type TeamChannel,
  type TelegramStatus,
  type WechatQrStatusResponse,
} from "@/lib/api";
import type { LucideIcon } from "lucide-react";

const LEAD_AGENT_ID = "system";

const EXTRA_NAV_LINKS: Array<{ href: string; icon: LucideIcon; label: string }> = [
  { href: "/lead/channels", icon: Radio, label: "Channels" },
];

function buildLeadThreadPath(threadId?: string | null) {
  if (!threadId) return "/lead";
  const params = new URLSearchParams({ thread: threadId });
  return `/lead?${params.toString()}`;
}

export default function ChannelsPage() {
  const router = useRouter();

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ["lead-channels"],
    queryFn: () => channelApi.listChannels(),
  });

  // Load threads for the sidebar
  const {
    data: threads = [],
    isLoading: isLoadingThreads,
    refetch: refetchThreads,
  } = useQuery({
    queryKey: ["leadChats"],
    queryFn: () => leadApi.listChats(),
  });

  const handleSelectThread = useCallback(
    (threadId: string) => {
      router.push(buildLeadThreadPath(threadId));
    },
    [router],
  );

  const handleNewThread = useCallback(() => {
    router.push("/lead?new=true");
  }, [router]);

  const handleUpdateTitle = useCallback(
    async (threadId: string, title: string) => {
      await leadApi.updateChatSummary(threadId, title);
      await refetchThreads();
    },
    [refetchThreads],
  );

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      await leadApi.deleteChat(threadId);
      await refetchThreads();
    },
    [refetchThreads],
  );

  const telegramChannel = channels.find((c) => c.channel_type === "telegram");
  const wechatChannel = channels.find((c) => c.channel_type === "wechat");

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar */}
      <ChatSidebar
        agentId={LEAD_AGENT_ID}
        activeTab="chat"
        threads={threads}
        currentThreadId={null}
        isNewThread={false}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onUpdateTitle={handleUpdateTitle}
        onDeleteThread={handleDeleteThread}
        isLoading={isLoadingThreads}
        hideNavLinks
        extraNavLinks={EXTRA_NAV_LINKS}
      />

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <h1 className="text-2xl font-bold">Channels</h1>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              <TelegramCard channel={telegramChannel} />
              <WechatCard channel={wechatChannel} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Telegram Card
// =============================================================================

function StatusBadge({ status }: { status: string | null | undefined }) {
  if (status === "listening") {
    return <Badge variant="default">Listening</Badge>;
  }
  if (status === "error") {
    return <Badge variant="destructive">Error</Badge>;
  }
  return <Badge variant="secondary">{status === "pending" ? "Connecting..." : "Disconnected"}</Badge>;
}

function TelegramCard({ channel }: { channel?: TeamChannel }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  const isConnected = !!channel && channel.enabled;

  // Poll telegram status when connected
  const { data: telegramStatus } = useQuery({
    queryKey: ["telegram-status"],
    queryFn: () => channelApi.getTelegramStatus(),
    enabled: isConnected,
    refetchInterval: 5000,
  });

  const removeWhitelistMutation = useMutation({
    mutationFn: (chatId: string) =>
      channelApi.removeTelegramWhitelist(chatId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["telegram-status"] });
    },
  });

  const handleSave = async () => {
    if (!token.trim()) return;
    setIsSaving(true);
    try {
      await channelApi.setChannel("telegram", { token: token.trim() });
      setToken("");
      await queryClient.invalidateQueries({ queryKey: ["lead-channels"] });
    } catch {
      // error handled by query
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await channelApi.deleteChannel("telegram");
      await queryClient.invalidateQueries({ queryKey: ["lead-channels"] });
      await queryClient.invalidateQueries({ queryKey: ["telegram-status"] });
    } catch {
      // error handled by query
    }
  };

  const handleCopyCode = async () => {
    if (!telegramStatus?.verification_code) return;
    await navigator.clipboard.writeText(telegramStatus.verification_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5 text-blue-500" />
          <h3 className="font-semibold">Telegram</h3>
        </div>
        {isConnected ? (
          <StatusBadge status={telegramStatus?.status} />
        ) : (
          <Badge variant="secondary">Disconnected</Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {isConnected ? (
          <>
            {/* Bot info */}
            {telegramStatus?.bot_username && (
              <p className="text-sm text-muted-foreground">
                Bot: @{telegramStatus.bot_username}
              </p>
            )}

            {/* Verification code */}
            {telegramStatus?.verification_code && (
              <div className="rounded-md border p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Verification Code:</span>
                  <code className="rounded bg-muted px-2 py-1 font-mono text-lg font-bold">
                    {telegramStatus.verification_code}
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={handleCopyCode}
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5 text-green-500" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Send this code from any new Telegram chat or group to activate it with your bot.
                </p>
              </div>
            )}

            {/* Whitelist */}
            {telegramStatus?.whitelist && telegramStatus.whitelist.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Verified Chats</h4>
                <div className="rounded-md border divide-y">
                  {telegramStatus.whitelist.map((entry) => (
                    <div
                      key={entry.chat_id}
                      className="flex items-center justify-between px-3 py-2 text-sm"
                    >
                      <div className="flex-1 min-w-0">
                        <span className="font-medium truncate block">
                          {entry.chat_name || entry.chat_id}
                        </span>
                        {entry.chat_name && (
                          <span className="text-xs text-muted-foreground">
                            {entry.chat_id}
                          </span>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                        onClick={() => removeWhitelistMutation.mutate(entry.chat_id)}
                        disabled={removeWhitelistMutation.isPending}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Disconnect */}
            <div className="flex justify-end">
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDelete}
              >
                <Trash2 className="h-4 w-4 mr-1" />
                Disconnect
              </Button>
            </div>
          </>
        ) : (
          <div className="flex gap-2">
            <Input
              placeholder="Bot token from @BotFather"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave();
              }}
            />
            <Button onClick={handleSave} disabled={!token.trim() || isSaving}>
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Connect"
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// WeChat Card
// =============================================================================

type WechatState =
  | { step: "idle" }
  | { step: "loading" }
  | { step: "qr"; qrcode: string; imgContent: string }
  | { step: "scanned" }
  | { step: "confirmed"; credentials: NonNullable<WechatQrStatusResponse> }
  | { step: "saving" }
  | { step: "error"; message: string };

function WechatCard({ channel }: { channel?: TeamChannel }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<WechatState>({ step: "idle" });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isConnected = !!channel && channel.enabled;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const startQrFlow = async () => {
    setState({ step: "loading" });
    try {
      const qr = await channelApi.getWechatQrCode();
      setState({
        step: "qr",
        qrcode: qr.qrcode,
        imgContent: qr.qrcode_img_content,
      });

      // Auto-expire QR after 5 minutes
      pollTimeoutRef.current = setTimeout(() => {
        stopPolling();
        setState({ step: "error", message: "QR code expired. Please try again." });
      }, 5 * 60 * 1000);

      // Start polling for scan status
      pollRef.current = setInterval(async () => {
        try {
          const status = await channelApi.pollWechatQrStatus(qr.qrcode);
          if (status.status === "confirmed" && status.bot_token) {
            stopPolling();
            setState({ step: "saving" });
            try {
              await channelApi.connectWechat({
                bot_token: status.bot_token,
                baseurl: status.baseurl || "https://ilinkai.weixin.qq.com",
                ilink_bot_id: status.ilink_bot_id || "",
                user_id: status.user_id || "",
              });
              await queryClient.invalidateQueries({
                queryKey: ["lead-channels"],
              });
              setState({ step: "idle" });
            } catch (saveErr) {
              setState({
                step: "error",
                message:
                  saveErr instanceof Error
                    ? saveErr.message
                    : "Failed to save credentials",
              });
            }
          } else if (status.status === "scanned") {
            setState((prev) =>
              prev.step === "qr" ? { step: "scanned" } : prev,
            );
          }
        } catch {
          // Keep polling on transient errors
        }
      }, 3000);
    } catch (err) {
      setState({
        step: "error",
        message: err instanceof Error ? err.message : "Failed to get QR code",
      });
    }
  };

  const handleDelete = async () => {
    try {
      await channelApi.deleteChannel("wechat");
      await queryClient.invalidateQueries({ queryKey: ["lead-channels"] });
    } catch {
      // error handled by query
    }
  };

  const handleCancel = () => {
    stopPolling();
    setState({ step: "idle" });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5 text-green-500" />
          <h3 className="font-semibold">WeChat</h3>
        </div>
        <Badge variant={isConnected ? "default" : "secondary"}>
          {isConnected ? "Connected" : "Disconnected"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {isConnected ? (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              WeChat bot connected
            </p>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
            >
              <Trash2 className="h-4 w-4 mr-1" />
              Disconnect
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {state.step === "idle" && (
              <Button onClick={startQrFlow}>Connect WeChat</Button>
            )}

            {state.step === "loading" && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Getting QR code...
              </div>
            )}

            {state.step === "qr" && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Scan this QR code with WeChat to connect:
                </p>
                <div className="flex justify-center">
                  <div className="p-3 bg-white rounded border">
                    <QRCodeSVG
                      value={state.imgContent || state.qrcode}
                      size={192}
                      level="M"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Waiting for scan...
                </div>
                <Button variant="ghost" size="sm" onClick={handleCancel}>
                  Cancel
                </Button>
              </div>
            )}

            {state.step === "scanned" && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Check className="h-4 w-4 text-green-500" />
                Scanned! Confirming...
              </div>
            )}

            {state.step === "saving" && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving credentials...
              </div>
            )}

            {state.step === "error" && (
              <div className="space-y-2">
                <p className="text-sm text-destructive">{state.message}</p>
                <Button variant="outline" size="sm" onClick={startQrFlow}>
                  Retry
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
