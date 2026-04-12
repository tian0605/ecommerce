BEGIN;

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS current_stage TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_status TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_started_at TIMESTAMP;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_updated_at TIMESTAMP;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_owner TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_result TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS blocked_reason TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS next_stage TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS source_stage TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS stage_context JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_tasks_stage_exec_priority_created
    ON tasks(current_stage, exec_state, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_tasks_root_source_stage_created
    ON tasks(root_task_id, source_stage, created_at);

CREATE INDEX IF NOT EXISTS idx_tasks_type_stage_exec
    ON tasks(task_type, current_stage, exec_state);

ALTER TABLE tasks
    ADD CONSTRAINT chk_tasks_current_stage
    CHECK (current_stage IS NULL OR current_stage IN ('idea', 'plan', 'build', 'review', 'test', 'release', 'retrospective'));

ALTER TABLE tasks
    ADD CONSTRAINT chk_tasks_stage_status
    CHECK (stage_status IS NULL OR stage_status IN ('ready', 'in_progress', 'blocked', 'passed', 'failed', 'done', 'retryable'));

UPDATE tasks
SET current_stage = CASE
        WHEN LOWER(COALESCE(exec_state, '')) = 'end' THEN 'retrospective'
        WHEN task_type = '修复' THEN 'build'
        WHEN task_type = '临时任务'
             AND COALESCE(NULLIF(BTRIM(success_criteria), ''), NULLIF(BTRIM(plan), '')) IS NULL THEN 'idea'
        WHEN task_type = '临时任务' THEN 'plan'
        ELSE 'plan'
    END,
    stage_status = CASE
        WHEN LOWER(COALESCE(exec_state, '')) = 'end' THEN 'done'
        WHEN LOWER(COALESCE(exec_state, '')) = 'processing' THEN 'in_progress'
        WHEN LOWER(COALESCE(exec_state, '')) IN ('error_fix_pending', 'normal_crash') THEN 'retryable'
        WHEN LOWER(COALESCE(exec_state, '')) = 'requires_manual' THEN 'blocked'
        ELSE 'ready'
    END,
    stage_started_at = COALESCE(stage_started_at, created_at, CURRENT_TIMESTAMP),
    stage_updated_at = COALESCE(stage_updated_at, updated_at, created_at, CURRENT_TIMESTAMP),
    next_stage = COALESCE(next_stage, CASE
        WHEN LOWER(COALESCE(exec_state, '')) = 'end' THEN NULL
        WHEN task_type = '修复' THEN 'review'
        WHEN task_type = '临时任务'
             AND COALESCE(NULLIF(BTRIM(success_criteria), ''), NULLIF(BTRIM(plan), '')) IS NULL THEN 'plan'
        ELSE 'build'
    END),
    stage_context = COALESCE(stage_context, '{}'::jsonb)
WHERE current_stage IS NULL
   OR stage_status IS NULL
   OR stage_started_at IS NULL
   OR stage_updated_at IS NULL
   OR stage_context IS NULL;

COMMIT;