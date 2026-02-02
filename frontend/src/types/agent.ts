/**
 * TypeScript types for Agent API responses
 */

export interface Agent {
  id: string;
  name: string | null;
  slug: string | null;
  picture: string | null;
  purpose: string | null;
  personality: string | null;
  principles: string | null;
  model: string;
  prompt: string | null;
  prompt_append: string | null;
  temperature: number | null;
  frequency_penalty: number | null;
  presence_penalty: number | null;
  wallet_provider: "cdp" | "native" | "readonly" | "safe" | "privy" | "none" | null;
  readonly_wallet_address: string | null;
  network_id: string | null;
  skills: Record<string, unknown> | null;
  version: string | null;
  statistics: Record<string, unknown> | null;
  assets: Record<string, unknown> | null;
  account_snapshot: CreditAccount | null;
  extra: Record<string, unknown> | null;
  deployed_at: string | null;
  public_info_updated_at: string | null;
  created_at: string;
  updated_at: string;

  // Flattened AgentResponse fields
  linked_twitter_username: string | null;
  linked_telegram_username: string | null;
  linked_twitter_name: string | null;
  linked_telegram_name: string | null;
  discord_username?: string | null; // Keeping as optional if needed by UI
}

export interface CreditAccount {
  id: string;
  owner_type: "user" | "agent" | "team" | "platform";
  owner_id: string;
  free_quota: string;
  refill_amount: string;
  free_credits: string;
  reward_credits: string;
  credits: string;
  total_income: string;
  total_expense: string;
  balance?: number; // Kept for backward compatibility if computed in UI
  credit_limit?: number; // Kept for backward compatibility
}

export interface AgentQuota {
  // Deprecated, keeping for temporary compatibility if needed
  daily_quota: number;
  daily_used: number;
  monthly_quota: number;
  monthly_used: number;
}

export type AgentResponse = Agent;

// API Error response
export interface ApiError {
  key: string;
  message: string;
}
