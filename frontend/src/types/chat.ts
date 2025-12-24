/**
 * Chat-related TypeScript types for IntentKit frontend
 */

export type AuthorType = "twitter" | "telegram" | "web" | "discord" | "api";

export interface ChatMessageAttachment {
  type: "link" | "image" | "file";
  url: string;
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
  search_mode?: boolean;
  super_mode?: boolean;
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

// UI-specific types
export interface UIMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  skillCalls?: ChatMessageSkillCall[];
}
