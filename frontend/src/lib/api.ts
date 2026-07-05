import type {
  ChatMessage,
  ChatMessagesResponse,
  ChatMessageToolCall,
  ChatThread,
} from "@/types/chat";
import type { AgentResponse } from "@/types/agent";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

/**
 * Generate a unique chat ID
 */
export function generateChatId(): string {
  return `chat_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Generate a unique user ID
 */
export function generateUserId(): string {
  // Check if we already have a user ID in localStorage
  if (typeof window !== "undefined") {
    const existingId = localStorage.getItem("intentkit_user_id");
    if (existingId) return existingId;

    const newId = `user_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    localStorage.setItem("intentkit_user_id", newId);
    return newId;
  }
  return `user_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Agent API functions
 */
export const agentApi = {
  /**
   * Get all agents
   */
  async getAll(): Promise<AgentResponse[]> {
    const response = await fetch(`${API_BASE}/agents`);
    if (!response.ok) {
      throw new Error(`Failed to fetch agents: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get agent schema for form generation
   */
  async getSchema(): Promise<Record<string, unknown>> {
    const response = await fetch(`${API_BASE}/schema/agent`);
    if (!response.ok) {
      throw new Error(`Failed to fetch agent schema: ${response.statusText}`);
    }
    const schema = await response.json();
    // Remove $schema field as AJV doesn't support draft-2020-12
    delete schema.$schema;
    return schema;
  },

  /**
   * Create a new agent
   */
  async create(data: Record<string, unknown>): Promise<AgentResponse> {
    const response = await fetch(`${API_BASE}/agents`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Failed to create agent: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Get a single agent by ID
   */
  async getById(agentId: string): Promise<AgentResponse> {
    const response = await fetch(`${API_BASE}/agents/${agentId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch agent: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get a single agent by ID with full editable fields
   */
  async getEditableById(agentId: string): Promise<Record<string, unknown>> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/editable`);
    if (!response.ok) {
      throw new Error(`Failed to fetch editable agent: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Patch an existing agent with partial updates
   * PATCH /api/agents/{agentId}
   */
  async patch(
    agentId: string,
    data: Record<string, unknown>,
  ): Promise<AgentResponse> {
    const response = await fetch(`${API_BASE}/agents/${agentId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Failed to update agent: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Upload an image for use as agent picture
   * POST /api/agents/upload-picture
   */
  async uploadPicture(file: File): Promise<{ path: string }> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/agents/upload-picture`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Failed to upload picture: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Archive an agent
   * PUT /api/agents/{agentId}/archive
   */
  async archive(agentId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/archive`, {
      method: "PUT",
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Failed to archive agent: ${response.statusText}`,
      );
    }
  },

  /**
   * Reactivate an archived agent
   * PUT /api/agents/{agentId}/reactivate
   */
  async reactivate(agentId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/reactivate`, {
      method: "PUT",
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail ||
          `Failed to reactivate agent: ${response.statusText}`,
      );
    }
  },
};

/**
 * LLM Model Info type definition
 */
export interface LLMModelInfo {
  id: string;
  name: string;
  provider: string;
  provider_name: string;
  enabled: boolean;
  input_price: string;
  output_price: string;
  price_level: number | null;
  context_length: number;
  output_length: number;
  intelligence: number;
  speed: number;
  supports_image_input: boolean;
  supports_audio_input: boolean;
  supports_video_input: boolean;
  supports_file_input: boolean;
}

/**
 * Metadata API functions
 */
export const metadataApi = {
  /**
   * Get all available LLM models
   * GET /metadata/llms
   */
  async getLLMs(): Promise<LLMModelInfo[]> {
    const response = await fetch(`${API_BASE}/metadata/llms`);
    if (!response.ok) {
      throw new Error(`Failed to fetch LLM models: ${response.statusText}`);
    }
    return response.json();
  },
};

/**
 * Chat API functions for local single-user mode
 * Based on app/local/chat.py endpoints:
 * - GET /agents/{aid}/chats - List chat threads
 * - POST /agents/{aid}/chats - Create new chat thread
 * - PATCH /agents/{aid}/chats/{chat_id} - Update chat summary
 * - DELETE /agents/{aid}/chats/{chat_id} - Delete chat thread
 * - GET /agents/{aid}/chats/{chat_id}/messages - List messages with pagination
 * - POST /agents/{aid}/chats/{chat_id}/messages - Send message (supports streaming)
 */
export const chatApi = {
  /**
   * List all chat threads for an agent
   * GET /agents/{aid}/chats
   */
  async listChats(agentId: string): Promise<ChatThread[]> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/chats`);
    if (!response.ok) {
      throw new Error(`Failed to list chats: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Create a new chat thread
   * POST /agents/{aid}/chats
   */
  async createChat(
    agentId: string,
    chatId?: string,
    firstMessage?: string,
  ): Promise<ChatThread> {
    const payload: { chat_id?: string; first_message?: string } = {};
    if (chatId) payload.chat_id = chatId;
    if (firstMessage) payload.first_message = firstMessage;
    const hasPayload = Object.keys(payload).length > 0;

    const response = await fetch(`${API_BASE}/agents/${agentId}/chats`, {
      method: "POST",
      headers: hasPayload ? { "Content-Type": "application/json" } : undefined,
      body: hasPayload ? JSON.stringify(payload) : undefined,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to create chat: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Update chat summary (title)
   * PATCH /agents/{aid}/chats/{chat_id}
   */
  async updateChatSummary(
    agentId: string,
    chatId: string,
    summary: string,
  ): Promise<ChatThread> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chats/${chatId}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ summary }),
      },
    );
    if (!response.ok) {
      throw new Error(`Failed to update chat summary: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Delete a chat thread
   * DELETE /agents/{aid}/chats/{chat_id}
   */
  async deleteChat(agentId: string, chatId: string): Promise<void> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chats/${chatId}`,
      {
        method: "DELETE",
      },
    );
    if (!response.ok) {
      throw new Error(`Failed to delete chat: ${response.statusText}`);
    }
  },

  /**
   * List messages in a chat thread with cursor-based pagination
   * GET /agents/{aid}/chats/{chat_id}/messages
   * Returns messages in DESC order (newest first)
   */
  async listMessages(
    agentId: string,
    chatId: string,
    cursor?: string,
    limit: number = 50,
  ): Promise<ChatMessagesResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) {
      params.append("cursor", cursor);
    }
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chats/${chatId}/messages?${params.toString()}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to list messages: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Send a message to a chat thread (non-streaming)
   * POST /agents/{aid}/chats/{chat_id}/messages
   */
  async sendMessage(
    agentId: string,
    chatId: string,
    message: string,
  ): Promise<ChatMessage[]> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chats/${chatId}/messages`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message, stream: false }),
      },
    );
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to send message: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Send a message with streaming response
   * POST /agents/{aid}/chats/{chat_id}/messages with stream: true
   * Returns an async generator that yields ChatMessage objects
   */
  async *sendMessageStream(
    agentId: string,
    chatId: string,
    message: string,
    signal?: AbortSignal,
  ): AsyncGenerator<ChatMessage, void, unknown> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chats/${chatId}/messages`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message, stream: true }),
        signal,
      },
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to send message: ${response.statusText}`,
      );
    }

    if (!response.body) {
      throw new Error("No response body for streaming");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventType === "message") {
            const data = line.slice(6);
            try {
              const message = JSON.parse(data) as ChatMessage;
              yield message;
            } catch {
              console.warn("Failed to parse SSE message:", data);
            }
            eventType = "";
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  /**
   * Cancel an in-progress generation
   * POST /agents/{aid}/chats/{chat_id}/cancel
   */
  async cancelGeneration(
    agentId: string,
    chatId: string,
  ): Promise<{ cancelled: boolean }> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chats/${chatId}/cancel`,
      {
        method: "POST",
      },
    );
    return response.json();
  },
};

/**
 * Lead Chat API functions
 * Based on app/local/lead.py endpoints:
 * - GET /lead/chats - List lead chat threads
 * - POST /lead/chats - Create new lead chat thread
 * - PATCH /lead/chats/{chat_id} - Update chat summary
 * - DELETE /lead/chats/{chat_id} - Delete chat thread
 * - GET /lead/chats/{chat_id}/messages - List messages with pagination
 * - POST /lead/chats/{chat_id}/messages - Send message (supports streaming)
 * - POST /lead/chats/{chat_id}/cancel - Cancel generation
 */
/**
 * Channel type definitions
 */
export interface TeamChannel {
  team_id: string;
  channel_type: string;
  enabled: boolean;
  config: Record<string, string> | null;
  owner_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface TelegramWhitelistEntry {
  chat_id: string;
  chat_name: string | null;
  verified_at: string;
}

export interface TelegramStatus {
  status: string | null;
  verification_code: string | null;
  bot_username: string | null;
  bot_name: string | null;
  whitelist: TelegramWhitelistEntry[];
}

export interface WechatQrCodeResponse {
  qrcode: string;
  qrcode_img_content: string;
}

export interface WechatQrStatusResponse {
  status: string;
  bot_token: string | null;
  baseurl: string | null;
  ilink_bot_id: string | null;
  user_id: string | null;
}

export interface DefaultChannelInfo {
  default_channel: string | null;
  default_channel_chat_id: string | null;
}

/**
 * Channel API functions for lead channel management
 */
export const channelApi = {
  async getDefaultChannel(): Promise<DefaultChannelInfo> {
    const response = await fetch(`${API_BASE}/lead/channel/default`);
    if (!response.ok) {
      throw new Error(
        `Failed to get default channel: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async listDefaultChannelMessages(
    cursor?: string,
    limit: number = 50,
  ): Promise<ChatMessagesResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) {
      params.append("cursor", cursor);
    }
    const response = await fetch(
      `${API_BASE}/lead/channel/default/messages?${params.toString()}`,
    );
    if (!response.ok) {
      throw new Error(
        `Failed to list default channel messages: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async listChannels(): Promise<TeamChannel[]> {
    const response = await fetch(`${API_BASE}/lead/channels`);
    if (!response.ok) {
      throw new Error(`Failed to list channels: ${response.statusText}`);
    }
    return response.json();
  },

  async setChannel(
    channelType: string,
    config: Record<string, string>,
  ): Promise<TeamChannel> {
    const response = await fetch(`${API_BASE}/lead/channels/${channelType}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to set channel: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async deleteChannel(channelType: string): Promise<void> {
    const response = await fetch(`${API_BASE}/lead/channels/${channelType}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(`Failed to delete channel: ${response.statusText}`);
    }
  },

  async getWechatQrCode(): Promise<WechatQrCodeResponse> {
    const response = await fetch(`${API_BASE}/wechat/qrcode`);
    if (!response.ok) {
      throw new Error(`Failed to get WeChat QR code: ${response.statusText}`);
    }
    return response.json();
  },

  async pollWechatQrStatus(qrcode: string): Promise<WechatQrStatusResponse> {
    const response = await fetch(
      `${API_BASE}/wechat/qrcode/status?qrcode=${encodeURIComponent(qrcode)}`,
    );
    if (!response.ok) {
      throw new Error(
        `Failed to poll WeChat QR status: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async connectWechat(credentials: {
    bot_token: string;
    baseurl: string;
    ilink_bot_id: string;
    user_id: string;
  }): Promise<TeamChannel> {
    const response = await fetch(`${API_BASE}/wechat/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    if (!response.ok) {
      throw new Error(`Failed to connect WeChat: ${response.statusText}`);
    }
    return response.json();
  },

  async getTelegramStatus(): Promise<TelegramStatus> {
    const response = await fetch(`${API_BASE}/lead/channels/telegram/status`);
    if (!response.ok) {
      throw new Error(`Failed to get Telegram status: ${response.statusText}`);
    }
    return response.json();
  },

  async removeTelegramWhitelist(chatId: string): Promise<void> {
    const response = await fetch(
      `${API_BASE}/lead/channels/telegram/whitelist/${encodeURIComponent(chatId)}`,
      { method: "DELETE" },
    );
    if (!response.ok) {
      throw new Error(`Failed to remove from whitelist: ${response.statusText}`);
    }
  },
};

// ---------------------------------------------------------------------------
// linkApi — external app accounts (Composio), used by the lead agent
// ---------------------------------------------------------------------------

export interface TeamLink {
  id: string;
  team_id: string;
  app: string;
  connected_account_id: string;
  status: string; // active | expired | revoked | ...
  account_label: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface LinkAppInfo {
  app: string;
  name: string;
  description: string;
  links: TeamLink[];
}

export interface TeamLinksResponse {
  enabled: boolean;
  apps: LinkAppInfo[];
}

export interface LinkCompleteResponse {
  team_id: string;
  app: string;
}

export const linkApi = {
  async listLinks(): Promise<TeamLinksResponse> {
    const response = await fetch(`${API_BASE}/lead/links`);
    if (!response.ok) {
      throw new Error(`Failed to list links: ${response.statusText}`);
    }
    return response.json();
  },

  // Start linking an account; returns the Composio auth URL to redirect to.
  async connectLink(app: string): Promise<{ url: string }> {
    const response = await fetch(
      `${API_BASE}/lead/links/${encodeURIComponent(app)}/connect`,
      { method: "POST" },
    );
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to start linking: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async deleteLink(linkId: string): Promise<void> {
    const response = await fetch(
      `${API_BASE}/lead/links/${encodeURIComponent(linkId)}`,
      { method: "DELETE" },
    );
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to unlink: ${response.statusText}`,
      );
    }
  },

  // Finish a link attempt: the OAuth landing page relays the
  // connected_account_id from Composio's callback redirect; the backend
  // verifies the account status against Composio directly.
  async completeLink(
    connectedAccountId: string,
  ): Promise<LinkCompleteResponse> {
    const response = await fetch(`${API_BASE}/lead/links/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connected_account_id: connectedAccountId }),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to complete link: ${response.statusText}`,
      );
    }
    return response.json();
  },
};

export const leadApi = {
  async getInfo(): Promise<AgentResponse> {
    const response = await fetch(`${API_BASE}/lead/info`);
    if (!response.ok) {
      throw new Error(`Failed to fetch lead info: ${response.statusText}`);
    }
    return response.json();
  },

  async listChats(): Promise<ChatThread[]> {
    const response = await fetch(`${API_BASE}/lead/chats`);
    if (!response.ok) {
      throw new Error(`Failed to list lead chats: ${response.statusText}`);
    }
    return response.json();
  },

  async createChat(
    chatId?: string,
    firstMessage?: string,
  ): Promise<ChatThread> {
    const payload: { chat_id?: string; first_message?: string } = {};
    if (chatId) payload.chat_id = chatId;
    if (firstMessage) payload.first_message = firstMessage;
    const hasPayload = Object.keys(payload).length > 0;

    const response = await fetch(`${API_BASE}/lead/chats`, {
      method: "POST",
      headers: hasPayload ? { "Content-Type": "application/json" } : undefined,
      body: hasPayload ? JSON.stringify(payload) : undefined,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message ||
          `Failed to create lead chat: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async updateChatSummary(
    chatId: string,
    summary: string,
  ): Promise<ChatThread> {
    const response = await fetch(`${API_BASE}/lead/chats/${chatId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ summary }),
    });
    if (!response.ok) {
      throw new Error(
        `Failed to update lead chat summary: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async deleteChat(chatId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/lead/chats/${chatId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(`Failed to delete lead chat: ${response.statusText}`);
    }
  },

  async listMessages(
    chatId: string,
    cursor?: string,
    limit: number = 50,
  ): Promise<ChatMessagesResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) {
      params.append("cursor", cursor);
    }
    const response = await fetch(
      `${API_BASE}/lead/chats/${chatId}/messages?${params.toString()}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to list lead messages: ${response.statusText}`);
    }
    return response.json();
  },

  async *sendMessageStream(
    chatId: string,
    message: string,
    signal?: AbortSignal,
  ): AsyncGenerator<ChatMessage, void, unknown> {
    const response = await fetch(
      `${API_BASE}/lead/chats/${chatId}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, stream: true }),
        signal,
      },
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message ||
          `Failed to send lead message: ${response.statusText}`,
      );
    }

    if (!response.body) {
      throw new Error("No response body for streaming");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventType === "message") {
            const data = line.slice(6);
            try {
              const message = JSON.parse(data) as ChatMessage;
              yield message;
            } catch {
              console.warn("Failed to parse SSE message:", data);
            }
            eventType = "";
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  async cancelGeneration(chatId: string): Promise<{ cancelled: boolean }> {
    const response = await fetch(`${API_BASE}/lead/chats/${chatId}/cancel`, {
      method: "POST",
    });
    return response.json();
  },
};

/**
 * Helper type for streaming state
 */
export interface StreamingState {
  isStreaming: boolean;
  currentToolCalls: ChatMessageToolCall[];
  pendingMessage: string;
}

/**
 * Activity type definition
 */
export interface ActivityItem {
  id: string;
  agent_id: string;
  agent_name?: string;
  agent_picture?: string;
  activity_type?: string;
  text: string;
  images?: string[];
  video?: string;
  link?: string;
  link_meta?: {
    title?: string;
    description?: string;
    image?: string;
    favicon?: string;
  };
  post_id?: string;
  description?: string; // Deprecated: distinct from text
  details?: Record<string, unknown>; // Deprecated
  created_at: string;
}

/**
 * Post type definition
 */
export interface PostItem {
  id: string;
  agent_id: string;
  agent_name?: string | null;
  agent_picture?: string | null;
  title: string;
  excerpt?: string;
  slug?: string;
  tags?: string[];
  markdown?: string;
  view_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * Activity API functions
 */
export const activityApi = {
  /**
   * Get all activities
   */
  async getAll(limit: number = 50): Promise<ActivityItem[]> {
    const response = await fetch(`${API_BASE}/activities?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch activities: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get activities for a specific agent
   * GET /agents/{agentId}/activities
   */
  async getByAgent(
    agentId: string,
    limit: number = 50,
  ): Promise<ActivityItem[]> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/activities?limit=${limit}`,
    );
    if (!response.ok) {
      throw new Error(
        `Failed to fetch agent activities: ${response.statusText}`,
      );
    }
    return response.json();
  },
};

/**
 * Post API functions
 */
export const postApi = {
  /**
   * Get all posts
   */
  async getAll(limit: number = 50): Promise<PostItem[]> {
    const response = await fetch(`${API_BASE}/posts?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch posts: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get posts for a specific agent
   * GET /agents/{agentId}/posts
   */
  async getByAgent(agentId: string, limit: number = 50): Promise<PostItem[]> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/posts?limit=${limit}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch agent posts: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get a single post by ID
   */
  async getById(postId: string): Promise<PostItem> {
    const response = await fetch(`${API_BASE}/posts/${postId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch post: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get a single post by Slug
   */
  async getBySlug(agentId: string, slug: string): Promise<PostItem> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/posts/slug/${slug}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch post by slug: ${response.statusText}`);
    }
    return response.json();
  },

  getPdfUrl(postId: string): string {
    return `${API_BASE}/posts/${postId}/pdf`;
  },

  getPdfUrlBySlug(agentId: string, slug: string): string {
    return `${API_BASE}/agents/${agentId}/posts/slug/${slug}/pdf`;
  },
};

/**
 * Subscription API functions
 */
export const subscriptionApi = {
  async list(): Promise<{ agent_id: string }[]> {
    const response = await fetch(`${API_BASE}/subscriptions`);
    if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
    return response.json();
  },

  async subscribe(agentId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/subscriptions/${agentId}`, {
      method: "POST",
    });
    if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
  },

  async unsubscribe(agentId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/subscriptions/${agentId}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
  },
};

/**
 * Public API - no auth required
 */
export const publicApi = {
  async getAgents(): Promise<AgentResponse[]> {
    const response = await fetch(`${API_BASE}/public/agents`);
    if (!response.ok) {
      throw new Error(`Failed to fetch public agents: ${response.statusText}`);
    }
    return response.json();
  },

  async getTimeline(limit = 20, cursor?: string | null) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", cursor);
    const response = await fetch(`${API_BASE}/public/timeline?${params}`);
    if (!response.ok) {
      throw new Error(
        `Failed to fetch public timeline: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async getPosts(limit = 20, cursor?: string | null) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", cursor);
    const response = await fetch(`${API_BASE}/public/posts?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch public posts: ${response.statusText}`);
    }
    return response.json();
  },

  async getPost(postId: string) {
    const response = await fetch(`${API_BASE}/public/posts/${postId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch public post: ${response.statusText}`);
    }
    return response.json();
  },
};

/**
 * Basic agent display info, resolved by the backend at read time.
 */
export interface AgentInfo {
  id: string;
  name?: string | null;
  picture?: string | null;
  slug?: string | null;
}

/**
 * Autonomous Task type definition
 */
export interface AutonomousTask {
  id: string;
  team_id?: string;
  target_agent_id?: string | null;
  target_agent?: AgentInfo | null;
  created_by?: string | null;
  name?: string;
  description?: string;
  cron?: string;
  prompt: string;
  enabled: boolean;
  has_memory: boolean;
  status?: string;
  next_run_time?: string;
  chat_id: string;
}

/**
 * One run of an autonomous task; its log is a group of chat messages.
 */
export interface AutonomousExecution {
  id: string;
  task_id: string;
  team_id: string;
  agent_id: string;
  target_agent_id?: string | null;
  chat_id: string;
  message_id: string;
  trigger: "cron" | "manual";
  triggered_by?: string | null;
  status: "running" | "success" | "error";
  error?: string | null;
  result?: string | null;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
  credit_cost?: number | string | null;
  message_count: number;
  cold_start_cost: number;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AutonomousExecutionsResponse {
  data: AutonomousExecution[];
  has_more: boolean;
  next_cursor: string | null;
}

/**
 * Autonomous API functions
 * Based on app/local/autonomous.py — tasks belong to the team.
 */
export const autonomousApi = {
  /**
   * List the team's autonomous tasks
   * GET /autonomous
   */
  async listTasks(): Promise<AutonomousTask[]> {
    const response = await fetch(`${API_BASE}/autonomous`);
    if (!response.ok) {
      throw new Error(
        `Failed to list autonomous tasks: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Create a new autonomous task
   * POST /autonomous
   */
  async createTask(
    data: Omit<AutonomousTask, "id" | "chat_id">,
  ): Promise<AutonomousTask> {
    const response = await fetch(`${API_BASE}/autonomous`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail ||
          `Failed to create autonomous task: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Update an autonomous task
   * PATCH /autonomous/{taskId}
   */
  async updateTask(
    taskId: string,
    data: Partial<AutonomousTask>,
  ): Promise<AutonomousTask> {
    const response = await fetch(`${API_BASE}/autonomous/${taskId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail ||
          `Failed to update autonomous task: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Get a single autonomous task
   * GET /autonomous/{taskId}
   */
  async getTask(taskId: string): Promise<AutonomousTask> {
    const response = await fetch(`${API_BASE}/autonomous/${taskId}`);
    if (!response.ok) {
      throw new Error(`Failed to get autonomous task: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Trigger one manual run of an autonomous task
   * POST /autonomous/{taskId}/execute
   */
  async executeTask(taskId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/autonomous/${taskId}/execute`, {
      method: "POST",
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.msg || `Failed to run task: ${response.statusText}`,
      );
    }
  },

  /**
   * List executions of an autonomous task, newest first
   * GET /autonomous/{taskId}/executions
   */
  async listExecutions(
    taskId: string,
    cursor?: string,
  ): Promise<AutonomousExecutionsResponse> {
    const params = new URLSearchParams();
    if (cursor) params.set("cursor", cursor);
    const query = params.toString();
    const response = await fetch(
      `${API_BASE}/autonomous/${taskId}/executions${query ? `?${query}` : ""}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to list executions: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get the chat message log of one execution, oldest first
   * GET /autonomous/{taskId}/executions/{executionId}/messages
   */
  async getExecutionMessages(
    taskId: string,
    executionId: string,
  ): Promise<ChatMessage[]> {
    const response = await fetch(
      `${API_BASE}/autonomous/${taskId}/executions/${executionId}/messages`,
    );
    if (!response.ok) {
      throw new Error(
        `Failed to get execution messages: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Delete an autonomous task
   * DELETE /autonomous/{taskId}
   */
  async deleteTask(taskId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/autonomous/${taskId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(
        `Failed to delete autonomous task: ${response.statusText}`,
      );
    }
  },
};

// ---------------------------------------------------------------------------
// Crypto Wallets (owned by the local system team)
// ---------------------------------------------------------------------------

export interface TeamWallet {
  id: string;
  team_id: string;
  name: string;
  wallet_provider: string; // cdp | native | readonly | safe | privy
  network_id: string | null;
  evm_wallet_address: string | null;
  solana_wallet_address: string | null;
  weekly_spending_limit: number | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface WalletCreateRequest {
  name: string;
  wallet_provider: string;
  network_id?: string | null;
  readonly_address?: string | null;
  weekly_spending_limit?: number | null;
}

export const walletApi = {
  async listWallets(): Promise<TeamWallet[]> {
    const response = await fetch(`${API_BASE}/wallets`);
    if (!response.ok) {
      throw new Error(`Failed to list wallets: ${response.statusText}`);
    }
    return response.json();
  },

  async createWallet(body: WalletCreateRequest): Promise<TeamWallet> {
    const response = await fetch(`${API_BASE}/wallets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.msg || errorData.message || `Failed to create wallet: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async renameWallet(walletId: string, name: string): Promise<TeamWallet> {
    const response = await fetch(`${API_BASE}/wallets/${walletId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.msg || errorData.message || `Failed to rename wallet: ${response.statusText}`,
      );
    }
    return response.json();
  },

  async deleteWallet(walletId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/wallets/${walletId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.msg || errorData.message || `Failed to delete wallet: ${response.statusText}`,
      );
    }
  },
};
