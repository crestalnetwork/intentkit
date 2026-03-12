-- Slug Refactoring Migration Script
-- Run this AFTER deploying the new code.

-- Pre-check: find any duplicate slugs that would block the unique index
SELECT slug, COUNT(*) FROM agents WHERE slug IS NOT NULL GROUP BY slug HAVING COUNT(*) > 1;

-- Constrain column type to VARCHAR(60)
ALTER TABLE agents ALTER COLUMN slug TYPE VARCHAR(60);

-- Add unique index (partial, only non-NULL slugs)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_agents_slug_unique
ON agents (slug) WHERE slug IS NOT NULL;
