-- name: list-job-logs
-- Paginated job log entries for a given job, ordered by sequence.
-- Queries the parent table; inheritance makes this transparent across all child tables.
SELECT
    jl.id,
    jl.job_id,
    jl.stage,
    jl.level,
    jl.message,
    jl.detail,
    jl.duration_ms,
    jl.sequence,
    jl.created_at,
    NULL::uuid AS team_id
FROM ONLY job_log jl


-- name: list-job-logs-all
-- Paginated job log entries for a given job across parent + child tables.
-- Default ordering by sequence ensures deterministic results when no sort filter is provided.
SELECT
    jl.id,
    jl.job_id,
    jl.stage,
    jl.level,
    jl.message,
    jl.detail,
    jl.duration_ms,
    jl.sequence,
    jl.created_at
FROM job_log jl
ORDER BY jl.sequence ASC


-- name: list-team-logs
-- Job logs for a specific team from team_job_log.
SELECT
    jl.id,
    jl.job_id,
    jl.stage,
    jl.level,
    jl.message,
    jl.detail,
    jl.duration_ms,
    jl.sequence,
    jl.created_at,
    jl.team_id
FROM team_job_log jl
WHERE jl.team_id = :team_id


-- name: get-job-log-summary
-- Aggregate summary per stage: worst level, latest message, entry count, duration.
SELECT
    jl.stage,
    (
        SELECT sub.level FROM job_log sub
        WHERE sub.job_id = jl.job_id AND sub.stage = jl.stage
        ORDER BY CASE sub.level
            WHEN 'ERROR' THEN 4
            WHEN 'WARNING' THEN 3
            WHEN 'INFO' THEN 2
            WHEN 'DEBUG' THEN 1
            ELSE 0
        END DESC, sub.sequence DESC
        LIMIT 1
    ) AS level,
    (
        SELECT sub.message FROM job_log sub
        WHERE sub.job_id = jl.job_id AND sub.stage = jl.stage
        ORDER BY sub.sequence DESC
        LIMIT 1
    ) AS message,
    SUM(COALESCE(jl.duration_ms, 0)) AS duration_ms,
    COUNT(*) AS entry_count,
    MIN(jl.sequence) AS sequence
FROM job_log jl
WHERE jl.job_id = :job_id
GROUP BY jl.job_id, jl.stage
ORDER BY MIN(jl.sequence) ASC
