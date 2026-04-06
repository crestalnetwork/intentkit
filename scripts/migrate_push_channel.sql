-- Push Channel Migration Script
-- Adds default_channel_chat_id column to teams table for push target tracking.

ALTER TABLE teams ADD COLUMN IF NOT EXISTS default_channel_chat_id VARCHAR;
