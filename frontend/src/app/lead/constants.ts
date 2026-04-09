import { Radio, MessageSquareText } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { DefaultChannelInfo } from "@/lib/api";

export const LEAD_AGENT_ID = "system";

export function buildLeadThreadPath(threadId?: string | null) {
  if (!threadId) return "/lead";
  const params = new URLSearchParams({ thread: threadId });
  return `/lead?${params.toString()}`;
}

export function buildExtraNavLinks(
  defaultChannelInfo?: DefaultChannelInfo | null,
): Array<{ href: string; icon: LucideIcon; label: string }> {
  const links: Array<{ href: string; icon: LucideIcon; label: string }> = [
    { href: "/lead/channels", icon: Radio, label: "Channels" },
  ];
  if (defaultChannelInfo?.default_channel_chat_id) {
    links.push({
      href: "/lead/channels/default",
      icon: MessageSquareText,
      label: "Default Channel",
    });
  }
  return links;
}

export const CHANNEL_DISPLAY_NAMES: Record<string, string> = {
  telegram: "Telegram",
  wechat: "WeChat",
};
