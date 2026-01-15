-- SQLSpec Migration
-- Version: 0002
-- Description: Add job table for background worker system
-- Created: 2025-11-02T00:00:00+00:00
-- Author: worker-system

-- name: migrate-0002-up
-- dialect: postgres

CREATE TABLE job (
    id uuid NOT NULL CONSTRAINT pk_job PRIMARY KEY DEFAULT gen_random_uuid(),
    key varchar(255) UNIQUE,
    function varchar(255) NOT NULL,
    data jsonb DEFAULT '{}',
    status varchar(50) NOT NULL DEFAULT 'pending',
    priority integer DEFAULT 0,
    max_retries integer DEFAULT 3,
    retry_count integer DEFAULT 0,
    scheduled_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL DEFAULT current_timestamp,
    started_at timestamp with time zone,
    heartbeat_at timestamp with time zone,
    completed_at timestamp with time zone,
    error text,
    result jsonb,
    metadata jsonb DEFAULT '{}'
);

COMMENT ON TABLE job IS 'Background job queue for worker system';
COMMENT ON COLUMN job.key IS 'Optional unique key for job deduplication';
COMMENT ON COLUMN job.function IS 'Name of the job function to execute';
COMMENT ON COLUMN job.data IS 'Job arguments as JSON';
COMMENT ON COLUMN job.status IS 'Current job status: pending, scheduled, running, completed, failed, cancelled';
COMMENT ON COLUMN job.priority IS 'Job priority (higher = more important)';
COMMENT ON COLUMN job.scheduled_at IS 'When to run the job (NULL = run immediately)';
COMMENT ON COLUMN job.heartbeat_at IS 'Last heartbeat timestamp for running tasks (for stale detection)';

-- Index for efficient querying of pending/scheduled jobs
CREATE INDEX idx_job_status ON job (status)
    WHERE status IN ('pending', 'scheduled');

-- Index for scheduled jobs
CREATE INDEX idx_job_scheduled_at ON job (scheduled_at)
    WHERE status = 'scheduled';

-- Index for job listing and cleanup
CREATE INDEX idx_job_created_at ON job (created_at);

-- Index for efficient stale task queries
CREATE INDEX idx_job_heartbeat_at ON job (heartbeat_at)
    WHERE status = 'running';

-- name: migrate-0002-down
-- dialect: postgres

DROP TABLE IF EXISTS job CASCADE;
