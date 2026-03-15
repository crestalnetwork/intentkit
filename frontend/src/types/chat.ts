/**
 * Chat-related TypeScript types for IntentKit frontend
 */

export type AuthorType =
  | "agent"
  | "skill"
  | "thinking"
  | "system"
  | "trigger"
  | "twitter"
  | "telegram"
  | "discord"
  | "web"
  | "api"
  | "xmtp"
  | "x402"
  | "internal";

export interface ChatMessageAttachment {
  type: "link" | "image" | "file" | "xmtp" | "card" | "choice";
  lead_text?: string | null;
  url?: string | null;
  json?: Record<string, unknown> | null;
  mime_type?: string;
  name?: string;
}

export interface ChatMessageSkillCall {
  id?: string;
  name: string;
  parameters: Record<string, unknown>;
  success: boolean;
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
  skill_calls?: ChatMessageSkillCall[];
  thinking?: string | null;
  error_type?: string | null;
  time_cost?: number;
  cold_start_cost?: number;
  attachments?: ChatMessageAttachment[];
  created_at: string;
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
  authorType === "web" || authorType === "api" || authorType === "trigger";

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
  skillCalls?: ChatMessageSkillCall[];
  attachments?: ChatMessageAttachment[];
}
