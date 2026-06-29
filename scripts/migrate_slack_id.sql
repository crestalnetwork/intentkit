-- Slack User ID Migration Script
-- Adds the slack_id column + index to the users table for the Slack channel.
--
-- The column is also auto-added by db_mig on startup (update_table_schema),
-- but that path does NOT create indexes, so run this on existing deployments
-- to keep User.get_by_slack_id() (hit on every inbound Slack message) indexed.
-- Idempotent: safe to run repeatedly.

ALTER TABLE users ADD COLUMN IF NOT EXISTS slack_id VARCHAR;
CREATE INDEX IF NOT EXISTS ix_users_slack_id ON users (slack_id);
