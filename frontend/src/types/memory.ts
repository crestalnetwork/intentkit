/**
 * TypeScript types for Memory API responses
 */

export interface Memory {
  id: string;
  agent_id: string;
  scope: "team" | "user" | "channel" | "cron";
  scope_key: string;
  content: string;
  created_at: string;
  updated_at: string;
  // Present on list responses; the update response omits them
  agent_name?: string | null;
  agent_picture?: string | null;
}
