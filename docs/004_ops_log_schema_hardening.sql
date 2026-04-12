BEGIN;

DROP VIEW IF EXISTS v_agent_logs;

ALTER TABLE main_logs
    ALTER COLUMN task_name TYPE VARCHAR(255),
    ALTER COLUMN log_type TYPE VARCHAR(50),
    ALTER COLUMN log_level TYPE VARCHAR(20),
    ALTER COLUMN run_status TYPE VARCHAR(50);

CREATE OR REPLACE VIEW v_agent_logs AS
WITH fallback_agents AS (
    SELECT
        (SELECT id FROM agents WHERE code = 'heartbeat-monitor') AS heartbeat_id,
        (SELECT id FROM agents WHERE code = 'system-unclassified') AS unknown_id
)
SELECT
    l.id AS log_id,
    COALESCE(l.agent_id, vt.agent_id, CASE WHEN COALESCE(l.log_type, '') = 'heartbeat' THEN fa.heartbeat_id ELSE fa.unknown_id END) AS agent_id,
    a.code AS agent_code,
    a.name AS agent_name,
    l.task_name,
    l.log_type,
    l.log_level,
    l.run_status,
    l.run_message,
    l.run_content,
    l.duration_ms,
    l.run_start_time,
    l.run_end_time,
    l.created_at
FROM main_logs l
CROSS JOIN fallback_agents fa
LEFT JOIN v_agent_tasks vt ON vt.task_name = l.task_name
LEFT JOIN agents a ON a.id = COALESCE(l.agent_id, vt.agent_id, CASE WHEN COALESCE(l.log_type, '') = 'heartbeat' THEN fa.heartbeat_id ELSE fa.unknown_id END);

COMMIT;