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
  wallet_provider: "cdp" | "readonly" | "none" | null;
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
}

export interface CreditAccount {
  balance: number;
  credit_limit: number;
}

export interface AgentQuota {
  daily_quota: number;
  daily_used: number;
  monthly_quota: number;
  monthly_used: number;
}

export interface AgentResponse extends Agent {
  quota: AgentQuota | null;
  twitter_username: string | null;
  telegram_username: string | null;
  discord_username: string | null;
}

// API Error response
export interface ApiError {
  key: string;
  message: string;
}
