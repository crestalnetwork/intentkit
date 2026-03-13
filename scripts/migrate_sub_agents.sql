-- Sub-Agents Migration Script
-- Adds sub_agents and sub_agent_prompt columns to agents, agent_drafts, and templates tables.

ALTER TABLE agents ADD COLUMN IF NOT EXISTS sub_agents JSONB;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS sub_agent_prompt TEXT;
ALTER TABLE agent_drafts ADD COLUMN IF NOT EXISTS sub_agents JSONB;
ALTER TABLE agent_drafts ADD COLUMN IF NOT EXISTS sub_agent_prompt TEXT;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS sub_agents JSONB;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS sub_agent_prompt TEXT;
