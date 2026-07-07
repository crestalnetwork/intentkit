/**
 * Chat-related TypeScript types for IntentKit frontend
 */

export type AuthorType =
  | "agent"
  | "tool"
  | "thinking"
  | "system"
  | "trigger"
  | "twitter"
  | "telegram"
  | "discord"
  | "web"
  | "api"
  | "wechat"
  | "xmtp"
  | "x402"
  | "internal";

export interface ChatMessageAttachment {
  type: "link" | "image" | "video" | "file" | "xmtp" | "card" | "choice";
  lead_text?: string | null;
  url?: string | null;
  json?: Record<string, unknown> | null;
  mime_type?: string;
  name?: string;
}

export interface ChatMessageToolCall {
  id?: string;
  name: string;
  parameters: Record<string, unknown>;
  /** Absent while the call is still running (pending frame) */
  success?: boolean;
  /** Agent-written status line shown to the user in place of the tool name */
  display_message?: string;
  response?: string;
  error_message?: string;
  credit_event_id?: string;
  credit_cost?: number;
}

export interface ChatMessageRequest {
  chat_id: string;
  app_id?: string;
  user_id: string;
  message: string;
  attachments?: ChatMessageAttachment[];
}

export interface ChatMessage {
  id: string;
  agent_id: string;
  chat_id: string;
  user_id?: string;
  author_id: string;
  author_type: AuthorType;
  thread_type: AuthorType;
  message: string;
  tool_calls?: ChatMessageToolCall[];
  thinking?: string | null;
  error_type?: string | null;
  time_cost?: number;
  cold_start_cost?: number;
  attachments?: ChatMessageAttachment[];
  created_at: string;
  /**
   * Transient stream frame: the tool calls are still executing. Never
   * persisted — result messages carrying the same tool call ids follow.
   */
  pending?: boolean;
}

export interface Chat {
  id: string;
  agent_id: string;
  user_id: string;
  summary?: string;
  rounds: number;
  created_at: string;
  updated_at: string;
}

// Alias for consistency with API naming
export type ChatThread = Chat;

export const isUserAuthoredMessage = (authorType: AuthorType) =>
  authorType === "web" ||
  authorType === "api" ||
  authorType === "trigger" ||
  authorType === "telegram" ||
  authorType === "wechat";

// Response type for paginated message list
export interface ChatMessagesResponse {
  data: ChatMessage[];
  has_more: boolean;
  next_cursor: string | null;
}

// UI-specific types
export interface UIMessage {
  id: string;
  role: "user" | "agent" | "system";
  authorType?: AuthorType;
  content: string;
  timestamp: Date;
  thinking?: string | null;
  errorType?: string | null;
  isStreaming?: boolean;
  toolCalls?: ChatMessageToolCall[];
  attachments?: ChatMessageAttachment[];
  /** Tool calls in this message are still executing (transient frame) */
  pending?: boolean;
}

/** Convert an API ChatMessage to the UI message shape. */
export function apiMessageToUIMessage(msg: ChatMessage): UIMessage {
  const isSystem = msg.author_type === "system";
  const isUserMessage = !isSystem && isUserAuthoredMessage(msg.author_type);
  return {
    id: msg.id,
    role: isSystem ? "system" : isUserMessage ? "user" : "agent",
    authorType: msg.author_type,
    content: msg.message,
    thinking: msg.thinking,
    errorType: msg.error_type,
    timestamp: new Date(msg.created_at),
    toolCalls: msg.tool_calls,
    attachments: msg.attachments,
    pending: msg.pending,
  };
}

/**
 * Fold a finished tool-result message into earlier pending tool frames:
 * remove the resolved calls (matched by tool call id) from every pending
 * message and drop pending messages that have no unresolved calls left.
 * Returns the list unchanged (same reference) unless `incoming` is a
 * finished tool message and the list still contains pending frames.
 */
export function foldToolResultMessage(
  messages: UIMessage[],
  incoming: UIMessage,
): UIMessage[] {
  if (incoming.authorType !== "tool" || incoming.pending) return messages;
  if (!messages.some((m) => m.pending)) return messages;
  const resolved = new Set(
    (incoming.toolCalls ?? []).map((c) => c.id).filter(Boolean),
  );
  if (resolved.size === 0) return messages;
  return messages
    .map((m) =>
      m.pending
        ? {
            ...m,
            toolCalls: (m.toolCalls ?? []).filter(
              (c) => !c.id || !resolved.has(c.id),
            ),
          }
        : m,
    )
    .filter((m) => !m.pending || (m.toolCalls?.length ?? 0) > 0);
}

/**
 * Drop leftover pending frames once a stream has ended: their calls never
 * reported a result, so they are not in the DB either. Returns the list
 * unchanged (same reference) when nothing is pending.
 */
export function dropPendingMessages(messages: UIMessage[]): UIMessage[] {
  return messages.some((m) => m.pending)
    ? messages.filter((m) => !m.pending)
    : messages;
}
