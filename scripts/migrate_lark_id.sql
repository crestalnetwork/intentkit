-- Lark/Feishu User ID Migration Script
-- Adds the lark_id column + index to the users table for the Lark channel.
--
-- The column is also auto-added by db_mig on startup (update_table_schema),
-- but that path does NOT create indexes, so run this on existing deployments
-- to keep User.get_by_lark_id() (hit on every inbound Lark message) indexed.
-- Idempotent: safe to run repeatedly.

ALTER TABLE users ADD COLUMN IF NOT EXISTS lark_id VARCHAR;
CREATE INDEX IF NOT EXISTS ix_users_lark_id ON users (lark_id);
