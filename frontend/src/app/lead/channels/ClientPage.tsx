"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, MessageCircle, Trash2, Loader2, Check } from "lucide-react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  channelApi,
  type TeamChannel,
  type WechatQrStatusResponse,
} from "@/lib/api";

export default function ChannelsPage() {
  const queryClient = useQueryClient();

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ["lead-channels"],
    queryFn: () => channelApi.listChannels(),
  });

  const telegramChannel = channels.find((c) => c.channel_type === "telegram");
  const wechatChannel = channels.find((c) => c.channel_type === "wechat");

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <div className="flex items-center gap-3">
            <Link href="/lead">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold">Channels</h1>
          </div>

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

function TelegramCard({ channel }: { channel?: TeamChannel }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const isConnected = !!channel && channel.enabled;

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
    } catch {
      // error handled by query
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5 text-blue-500" />
          <h3 className="font-semibold">Telegram</h3>
        </div>
        <Badge variant={isConnected ? "default" : "secondary"}>
          {isConnected ? "Connected" : "Disconnected"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {isConnected ? (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Bot token configured
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
