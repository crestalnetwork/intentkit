import type {
  ChatMessage,
  ChatMessageRequest,
  ChatMessageSkillCall,
} from "@/types/chat";
import type { AgentResponse } from "@/types/agent";

const API_BASE = "/api";

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
      throw new Error(errorData.detail || `Failed to create agent: ${response.statusText}`);
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
};

/**
 * Chat API functions
 * Based on web.py endpoints:
 * - POST /agents/{aid}/chat/v2 - Send message and get response
 * - GET /agents/{aid}/chat/history?chat_id={chat_id} - Get chat history
 * - GET /agents/{aid}/chats?user_id={user_id} - Get user's chat list
 * - POST /agents/{aid}/chat/retry/v2?chat_id={chat_id} - Retry last message
 */
export const chatApi = {
  /**
   * Send a message and get agent's response
   * POST /agents/{aid}/chat/v2
   * The chat is created automatically on first message
   */
  async sendMessage(
    agentId: string,
    request: ChatMessageRequest,
  ): Promise<ChatMessage[]> {
    const response = await fetch(`${API_BASE}/agents/${agentId}/chat/v2`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `Failed to send message: ${response.statusText}`,
      );
    }
    return response.json();
  },

  /**
   * Get chat history for a specific chat
   * GET /agents/{aid}/chat/history?chat_id={chat_id}&user_id={user_id}
   */
  async getChatHistory(
    agentId: string,
    chatId: string,
    userId?: string,
  ): Promise<ChatMessage[]> {
    const params = new URLSearchParams({ chat_id: chatId });
    if (userId) {
      params.append("user_id", userId);
    }
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chat/history?${params.toString()}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to get chat history: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get all chats for a user with a specific agent
   * GET /agents/{aid}/chats?user_id={user_id}
   */
  async getUserChats(
    agentId: string,
    userId: string,
  ): Promise<
    {
      id: string;
      agent_id: string;
      user_id: string;
      summary?: string;
      rounds: number;
      created_at: string;
      updated_at: string;
    }[]
  > {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chats?user_id=${encodeURIComponent(userId)}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to get user chats: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Retry the last message in a chat
   * POST /agents/{aid}/chat/retry/v2?chat_id={chat_id}
   */
  async retryChat(agentId: string, chatId: string): Promise<ChatMessage[]> {
    const response = await fetch(
      `${API_BASE}/agents/${agentId}/chat/retry/v2?chat_id=${encodeURIComponent(chatId)}`,
      {
        method: "POST",
      },
    );
    if (!response.ok) {
      throw new Error(`Failed to retry chat: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Update chat summary
   * PATCH /agents/{aid}/chats/{chat_id}
   */
  async updateChatSummary(
    agentId: string,
    chatId: string,
    summary: string,
  ): Promise<{
    id: string;
    agent_id: string;
    user_id: string;
    summary?: string;
    rounds: number;
    created_at: string;
    updated_at: string;
  }> {
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
   * Delete a chat
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
};

/**
 * Helper type for streaming state (for future use if streaming is added)
 */
export interface StreamingState {
  isStreaming: boolean;
  currentSkillCalls: ChatMessageSkillCall[];
  pendingMessage: string;
}
