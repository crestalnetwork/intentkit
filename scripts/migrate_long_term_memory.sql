-- Long-Term Memory Migration Script
-- Adds long_term_memory column to agent_data table
-- and enable_long_term_memory column to agents, agent_drafts, and templates tables.

ALTER TABLE agent_data ADD COLUMN IF NOT EXISTS long_term_memory TEXT;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS enable_long_term_memory BOOLEAN;
ALTER TABLE agent_drafts ADD COLUMN IF NOT EXISTS enable_long_term_memory BOOLEAN;
ALTER TABLE templates ADD COLUMN IF NOT EXISTS enable_long_term_memory BOOLEAN;
