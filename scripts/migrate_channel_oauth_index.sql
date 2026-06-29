-- Centralized-channel routing indexes (Slack workspace / Lark tenant → team).
--
-- The Slack/Lark webhook services resolve the owning team by
-- config->>'workspace_id' / config->>'tenant_key' on EVERY inbound event, so
-- index those JSONB expressions (otherwise it's a sequential scan per event).
--
-- UNIQUE so one Slack workspace / Lark enterprise can be bound to at most one
-- team: this also prevents an OAuth "confused deputy" from re-binding an
-- already-connected workspace to a different team (the second install fails
-- closed instead of hijacking it). db_mig does not create expression indexes,
-- so run this on existing deployments. Idempotent.

CREATE UNIQUE INDEX IF NOT EXISTS ix_team_channels_slack_workspace
    ON team_channels ((config ->> 'workspace_id'))
    WHERE channel_type = 'slack';

CREATE UNIQUE INDEX IF NOT EXISTS ix_team_channels_lark_tenant
    ON team_channels ((config ->> 'tenant_key'))
    WHERE channel_type = 'lark';
