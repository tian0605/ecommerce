BEGIN;

CREATE TABLE IF NOT EXISTS agents (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    owner TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    description TEXT,
    source_system TEXT NOT NULL DEFAULT 'openclaw',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agents_type_status ON agents(type, status);

INSERT INTO agents (code, name, type, owner, description)
VALUES
    ('workflow-runner', 'Workflow Runner', 'workflow', 'system', '负责常规工作流任务执行'),
    ('fix-executor', 'Fix Executor', 'fixer', 'system', '负责修复类任务执行'),
    ('heartbeat-monitor', 'Heartbeat Monitor', 'monitor', 'system', '负责心跳采集与监控'),
    ('temp-agent', 'Temp Agent', 'temp', 'system', '负责临时任务执行'),
    ('system-unclassified', 'System Unclassified', 'system', 'system', '无法确定归因时的兜底 agent')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS heartbeat_events (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT REFERENCES agents(id),
    source TEXT NOT NULL,
    heartbeat_status TEXT NOT NULL,
    summary TEXT,
    raw_report TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    pending_count INTEGER NOT NULL DEFAULT 0,
    processing_count INTEGER NOT NULL DEFAULT 0,
    requires_manual_count INTEGER NOT NULL DEFAULT 0,
    overtime_temp_count INTEGER NOT NULL DEFAULT 0,
    failed_recent_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    host_name TEXT,
    report_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_events_agent_time ON heartbeat_events(agent_id, report_time DESC);
CREATE INDEX IF NOT EXISTS idx_heartbeat_events_status_time ON heartbeat_events(heartbeat_status, report_time DESC);

CREATE TABLE IF NOT EXISTS agent_attribution_rules (
    id BIGSERIAL PRIMARY KEY,
    rule_name TEXT NOT NULL,
    match_scope TEXT NOT NULL,
    match_type TEXT NOT NULL,
    match_field TEXT,
    match_expr TEXT NOT NULL,
    agent_id BIGINT NOT NULL REFERENCES agents(id),
    priority INTEGER NOT NULL DEFAULT 100,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    stop_on_match BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rule_name)
);

CREATE INDEX IF NOT EXISTS idx_agent_attribution_rules_scope_enabled_priority
    ON agent_attribution_rules(match_scope, enabled, priority);

CREATE TABLE IF NOT EXISTS dashboard_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_scope TEXT NOT NULL,
    agent_id BIGINT REFERENCES agents(id),
    metric_name TEXT NOT NULL,
    metric_window TEXT NOT NULL,
    metric_value NUMERIC(18, 4) NOT NULL DEFAULT 0,
    metric_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    calculated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    UNIQUE(metric_scope, agent_id, metric_name, metric_window)
);

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS agent_id BIGINT REFERENCES agents(id);
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS attribution_source TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS attribution_version TEXT;

ALTER TABLE main_logs ADD COLUMN IF NOT EXISTS agent_id BIGINT REFERENCES agents(id);
ALTER TABLE main_logs ADD COLUMN IF NOT EXISTS attribution_source TEXT;
ALTER TABLE main_logs ADD COLUMN IF NOT EXISTS attribution_version TEXT;

CREATE INDEX IF NOT EXISTS idx_tasks_agent_id_created_at ON tasks(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_main_logs_agent_id_created_at ON main_logs(agent_id, created_at DESC);

INSERT INTO agent_attribution_rules (rule_name, match_scope, match_type, match_field, match_expr, agent_id, priority, notes)
SELECT 'task-auto-listing-prefix', 'task', 'prefix', 'task_name', 'AUTO-LISTING', a.id, 100, 'AUTO-LISTING 任务归属于 workflow-runner'
FROM agents a WHERE a.code = 'workflow-runner'
ON CONFLICT (rule_name) DO NOTHING;

INSERT INTO agent_attribution_rules (rule_name, match_scope, match_type, match_field, match_expr, agent_id, priority, notes)
SELECT 'task-fix-prefix', 'task', 'prefix', 'task_name', 'FIX-', a.id, 110, 'FIX- 任务归属于 fix-executor'
FROM agents a WHERE a.code = 'fix-executor'
ON CONFLICT (rule_name) DO NOTHING;

INSERT INTO agent_attribution_rules (rule_name, match_scope, match_type, match_field, match_expr, agent_id, priority, notes)
SELECT 'task-temp-type', 'task', 'field_equals', 'task_type', '临时任务', a.id, 120, '临时任务归属于 temp-agent'
FROM agents a WHERE a.code = 'temp-agent'
ON CONFLICT (rule_name) DO NOTHING;

INSERT INTO agent_attribution_rules (rule_name, match_scope, match_type, match_field, match_expr, agent_id, priority, notes)
SELECT 'log-heartbeat-type', 'log', 'field_equals', 'log_type', 'heartbeat', a.id, 100, 'heartbeat 类型日志归属于 heartbeat-monitor'
FROM agents a WHERE a.code = 'heartbeat-monitor'
ON CONFLICT (rule_name) DO NOTHING;

CREATE OR REPLACE VIEW v_agent_tasks AS
WITH parent_tasks AS (
    SELECT task_name, agent_id FROM tasks
), root_tasks AS (
    SELECT task_name, agent_id FROM tasks
), fallback_agents AS (
    SELECT
        (SELECT id FROM agents WHERE code = 'workflow-runner') AS workflow_id,
        (SELECT id FROM agents WHERE code = 'fix-executor') AS fix_id,
        (SELECT id FROM agents WHERE code = 'temp-agent') AS temp_id,
        (SELECT id FROM agents WHERE code = 'heartbeat-monitor') AS heartbeat_id,
        (SELECT id FROM agents WHERE code = 'system-unclassified') AS unknown_id
)
SELECT
    t.task_name,
    COALESCE(
        t.agent_id,
        pt.agent_id,
        rt.agent_id,
        CASE
            WHEN t.task_name LIKE 'AUTO-LISTING%' THEN fa.workflow_id
            WHEN t.task_name LIKE 'FIX-%' THEN fa.fix_id
            WHEN COALESCE(t.task_type, '') = '临时任务' THEN fa.temp_id
            WHEN COALESCE(t.fix_suggestion, '') ILIKE '%miaoshou-updater%' THEN fa.workflow_id
            ELSE fa.unknown_id
        END
    ) AS agent_id,
    a.code AS agent_code,
    a.name AS agent_name,
    t.display_name,
    t.task_type,
    t.priority,
    t.status,
    t.exec_state,
    t.task_level,
    t.parent_task_id,
    t.root_task_id,
    t.retry_count,
    t.last_error,
    t.notification_status,
    t.feedback_doc_url,
    t.feedback_markdown_file,
    t.created_at,
    t.updated_at
FROM tasks t
CROSS JOIN fallback_agents fa
LEFT JOIN parent_tasks pt ON pt.task_name = t.parent_task_id
LEFT JOIN root_tasks rt ON rt.task_name = t.root_task_id
LEFT JOIN agents a ON a.id = COALESCE(
    t.agent_id,
    pt.agent_id,
    rt.agent_id,
    CASE
        WHEN t.task_name LIKE 'AUTO-LISTING%' THEN fa.workflow_id
        WHEN t.task_name LIKE 'FIX-%' THEN fa.fix_id
        WHEN COALESCE(t.task_type, '') = '临时任务' THEN fa.temp_id
        WHEN COALESCE(t.fix_suggestion, '') ILIKE '%miaoshou-updater%' THEN fa.workflow_id
        ELSE fa.unknown_id
    END
);

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

CREATE OR REPLACE VIEW v_agent_heartbeats AS
SELECT
    h.id AS heartbeat_id,
    h.agent_id,
    a.code AS agent_code,
    a.name AS agent_name,
    h.heartbeat_status,
    h.summary,
    h.pending_count,
    h.processing_count,
    h.requires_manual_count,
    h.overtime_temp_count,
    h.failed_recent_count,
    h.duration_ms,
    h.host_name,
    h.report_time,
    h.created_at
FROM heartbeat_events h
LEFT JOIN agents a ON a.id = h.agent_id;

COMMIT;