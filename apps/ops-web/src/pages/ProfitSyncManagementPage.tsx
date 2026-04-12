import { Fragment, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  createProfitSyncTask,
  fetchRecentProfitSyncTasks,
  fetchTask,
  fetchTaskLogs,
} from '../api';
import { WorkspaceSidebar } from '../components/WorkspaceSidebar';
import type { TaskDetailView } from '../types';

const SYNC_TASK_PAGE_SIZE = 10;

function PageState(props: { title: string; detail: string }) {
  return (
    <div className="state-card">
      <div>
        <strong>{props.title}</strong>
        <p>{props.detail}</p>
      </div>
    </div>
  );
}

function formatTime(value?: string | null) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function buildVisiblePages(page: number, totalPages: number) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, totalPages, page - 1, page, page + 1]);
  if (page <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }
  if (page >= totalPages - 2) {
    pages.add(totalPages - 1);
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  }

  return Array.from(pages)
    .filter((value) => value >= 1 && value <= totalPages)
    .sort((left, right) => left - right);
}

function PaginationControls(props: { page: number; hasMore: boolean; total: number; pageSize: number; onPrev: () => void; onNext: () => void; onSelectPage: (page: number) => void }) {
  const totalPages = Math.max(1, Math.ceil(props.total / props.pageSize));
  const visiblePages = buildVisiblePages(props.page, totalPages);

  return (
    <div className="pagination-bar">
      <button className="ghost-button" onClick={props.onPrev} disabled={props.page <= 1}>上一页</button>
      {visiblePages.map((pageNumber, index) => {
        const previousPage = visiblePages[index - 1];
        const showGap = previousPage != null && pageNumber - previousPage > 1;
        return (
          <Fragment key={pageNumber}>
            {showGap ? <span className="pagination-gap">...</span> : null}
            <button className={`ghost-button page-number-button ${pageNumber === props.page ? 'active' : ''}`} onClick={() => props.onSelectPage(pageNumber)} disabled={pageNumber === props.page}>{pageNumber}</button>
          </Fragment>
        );
      })}
      <span>第 {props.page} / {totalPages} 页</span>
      <button className="ghost-button" onClick={props.onNext} disabled={!props.hasMore}>下一页</button>
    </div>
  );
}

function normalizeIds(text: string) {
  const items = text.replace(/\n/g, ',').split(',').map((item) => item.trim()).filter(Boolean);
  return Array.from(new Set(items));
}

export function ProfitSyncManagementPage() {
  const [searchParams] = useSearchParams();
  const [syncIdsText, setSyncIdsText] = useState('');
  const [targetProfitRate, setTargetProfitRate] = useState('0.20');
  const [syncPriority, setSyncPriority] = useState('P1');
  const [syncNote, setSyncNote] = useState('');
  const [selectedSyncTaskName, setSelectedSyncTaskName] = useState<string | null>(null);
  const [syncTaskPage, setSyncTaskPage] = useState(1);
  const [syncTaskKeyword, setSyncTaskKeyword] = useState('');
  const [syncTaskExecState, setSyncTaskExecState] = useState('');
  const [syncTaskPriority, setSyncTaskPriority] = useState('');

  useEffect(() => {
    const ids = searchParams.get('ids');
    if (ids) {
      setSyncIdsText((current) => current.trim() ? current : decodeURIComponent(ids).split(',').join('\n'));
    }
  }, [searchParams]);

  const normalizedSyncIds = useMemo(() => normalizeIds(syncIdsText), [syncIdsText]);

  const recentSyncTasksQuery = useQuery({
    queryKey: ['profit-sync-recent', syncTaskPage, syncTaskKeyword, syncTaskExecState, syncTaskPriority],
    queryFn: () => fetchRecentProfitSyncTasks({
      page: syncTaskPage,
      pageSize: SYNC_TASK_PAGE_SIZE,
      keyword: syncTaskKeyword,
      execState: syncTaskExecState || undefined,
      priority: syncTaskPriority || undefined,
    }),
    refetchInterval: 15000,
  });

  useEffect(() => {
    if (!selectedSyncTaskName && recentSyncTasksQuery.data?.items?.length) {
      setSelectedSyncTaskName(recentSyncTasksQuery.data.items[0].task_name);
    }
  }, [recentSyncTasksQuery.data, selectedSyncTaskName]);

  const syncTaskDetailQuery = useQuery({
    queryKey: ['profit-sync-task', selectedSyncTaskName],
    queryFn: () => fetchTask(selectedSyncTaskName as string),
    enabled: selectedSyncTaskName != null,
    refetchInterval: (query) => {
      const data = query.state.data as TaskDetailView | undefined;
      const execState = (data?.exec_state ?? '').toLowerCase();
      return execState === 'new' || execState === 'processing' ? 5000 : false;
    },
  });

  const syncTaskLogsQuery = useQuery({
    queryKey: ['profit-sync-task-logs', selectedSyncTaskName],
    queryFn: () => fetchTaskLogs(selectedSyncTaskName as string, 60),
    enabled: selectedSyncTaskName != null,
    refetchInterval: () => {
      const execState = (syncTaskDetailQuery.data?.exec_state ?? '').toLowerCase();
      return execState === 'new' || execState === 'processing' ? 8000 : false;
    },
  });

  const syncMutation = useMutation({
    mutationFn: () => createProfitSyncTask({
      alibaba_ids: normalizedSyncIds,
      profit_rate: Number(targetProfitRate) || 0.2,
      priority: syncPriority,
      note: syncNote.trim() || undefined,
      source: 'ops-web',
    }),
    onSuccess: (response) => {
      setSelectedSyncTaskName(response.task.task_name);
    },
  });

  const syncTask = syncTaskDetailQuery.data;

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Feishu Sync</span>
          <h1>飞书同步管理</h1>
          <p>独立管理利润明细到飞书的同步任务、历史记录、执行摘要与日志。</p>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Feishu Sync</span>
            <h2>飞书同步管理</h2>
            <p>同步指定商品利润明细到飞书分析表；如果从利润明细页进入，这里会自动带入选中的商品 ID。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill warning">task-based</span>
            <span className="status-pill success">feishu</span>
            <span className="status-pill success">background sync</span>
          </div>
        </section>

        <section className="profit-sync-layout">
          <div className="profit-sync-main">
            <div className="table-card">
              <div className="section-head"><h3>创建同步任务</h3><span>{normalizedSyncIds.length} IDs</span></div>
              <div className="form-grid">
                <label className="form-field form-field-full">
                  <span>1688商品ID</span>
                  <textarea className="form-textarea" rows={8} value={syncIdsText} onChange={(event) => setSyncIdsText(event.target.value)} placeholder="逗号或换行分隔多个 alibaba_id" />
                </label>
                <label className="form-field">
                  <span>目标利润率</span>
                  <input className="filter-input" value={targetProfitRate} onChange={(event) => setTargetProfitRate(event.target.value)} placeholder="0.20" />
                </label>
                <label className="form-field">
                  <span>优先级</span>
                  <select className="filter-select" value={syncPriority} onChange={(event) => setSyncPriority(event.target.value)}>
                    <option value="P0">P0</option>
                    <option value="P1">P1</option>
                    <option value="P2">P2</option>
                  </select>
                </label>
                <label className="form-field form-field-full">
                  <span>备注</span>
                  <textarea className="form-textarea" rows={4} value={syncNote} onChange={(event) => setSyncNote(event.target.value)} placeholder="同步批次说明" />
                </label>
              </div>
              <div className="form-actions">
                <button className="ghost-button" disabled={normalizedSyncIds.length === 0 || syncMutation.isPending} onClick={() => syncMutation.mutate()}>
                  {syncMutation.isPending ? '创建中...' : '创建同步任务'}
                </button>
                <span className="inline-meta">{syncMutation.error instanceof Error ? syncMutation.error.message : `当前将同步 ${normalizedSyncIds.length} 个商品 ID 到飞书`}</span>
              </div>
            </div>

            <div className="table-card">
              <div className="section-head"><h3>最近同步任务</h3><span>{recentSyncTasksQuery.data?.total ?? 0}</span></div>
              <div className="filters-panel task-history-filters">
                <input className="filter-input" value={syncTaskKeyword} onChange={(event) => { setSyncTaskKeyword(event.target.value); setSyncTaskPage(1); }} placeholder="搜索任务名 / 首个ID / 步骤" />
                <select className="filter-select" value={syncTaskExecState} onChange={(event) => { setSyncTaskExecState(event.target.value); setSyncTaskPage(1); }}>
                  <option value="">全部状态</option>
                  <option value="new">new</option>
                  <option value="processing">processing</option>
                  <option value="end">end</option>
                  <option value="error_fix_pending">error_fix_pending</option>
                  <option value="normal_crash">normal_crash</option>
                </select>
                <select className="filter-select" value={syncTaskPriority} onChange={(event) => { setSyncTaskPriority(event.target.value); setSyncTaskPage(1); }}>
                  <option value="">全部优先级</option>
                  <option value="P0">P0</option>
                  <option value="P1">P1</option>
                  <option value="P2">P2</option>
                </select>
              </div>
              {recentSyncTasksQuery.isLoading ? (
                <PageState title="正在加载同步任务" detail="读取最近的 PROFIT-SYNC 后台任务。" />
              ) : recentSyncTasksQuery.isError ? (
                <PageState title="同步任务加载失败" detail={recentSyncTasksQuery.error instanceof Error ? recentSyncTasksQuery.error.message : 'unknown error'} />
              ) : (
                <div className="panel-column">
                  <div className="profit-task-list">
                    {(recentSyncTasksQuery.data?.items ?? []).map((item) => (
                      <button key={item.task_name} className={`record-item ${selectedSyncTaskName === item.task_name ? 'active' : ''}`} onClick={() => setSelectedSyncTaskName(item.task_name)}>
                        <div className="record-item-head">
                          <strong>{item.display_name ?? item.task_name}</strong>
                          <span className={`status-pill ${item.exec_state === 'end' ? 'success' : item.exec_state === 'processing' || item.exec_state === 'new' ? 'warning' : 'danger'}`}>{item.exec_state ?? 'unknown'}</span>
                        </div>
                        <p>{item.current_step ?? item.current_stage ?? '等待执行'}</p>
                        <div className="inline-meta">{item.product_count ?? 0} IDs · 利润率 {item.profit_rate ?? 'N/A'} · {item.priority ?? 'P1'} · {formatTime(item.updated_at)}</div>
                      </button>
                    ))}
                  </div>
                  <PaginationControls
                    page={recentSyncTasksQuery.data?.page ?? syncTaskPage}
                    hasMore={recentSyncTasksQuery.data?.has_more ?? false}
                    total={recentSyncTasksQuery.data?.total ?? 0}
                    pageSize={recentSyncTasksQuery.data?.page_size ?? SYNC_TASK_PAGE_SIZE}
                    onPrev={() => setSyncTaskPage((current) => Math.max(1, current - 1))}
                    onNext={() => { if (recentSyncTasksQuery.data?.has_more) setSyncTaskPage((current) => current + 1); }}
                    onSelectPage={(value) => setSyncTaskPage(value)}
                  />
                </div>
              )}
            </div>
          </div>

          <div className="profit-sync-side">
            <div className="table-card">
              <div className="section-head"><h3>同步任务摘要</h3><span>{syncTask?.task_name ?? '未选择'}</span></div>
              {!syncTask ? (
                <PageState title="暂无同步任务" detail="创建或选择一个利润同步任务后，这里会展示执行状态和日志。" />
              ) : (
                <div className="panel-column">
                  <div className="key-value-grid">
                    <div><span className="metric-label">执行状态</span><strong>{syncTask.exec_state ?? 'N/A'}</strong></div>
                    <div><span className="metric-label">阶段状态</span><strong>{syncTask.stage_status ?? 'N/A'}</strong></div>
                    <div><span className="metric-label">当前步骤</span><strong>{syncTask.progress_checkpoint?.current_step ?? 'N/A'}</strong></div>
                    <div><span className="metric-label">最近更新</span><strong>{formatTime(syncTask.updated_at)}</strong></div>
                  </div>
                  <div className="record-item static"><strong>任务结果</strong><p>{syncTask.stage_result ?? syncTask.last_error ?? '等待结果'}</p></div>
                </div>
              )}
            </div>

            <div className="table-card">
              <div className="section-head"><h3>同步日志</h3><span>{syncTaskLogsQuery.data?.items?.length ?? 0}</span></div>
              {syncTaskLogsQuery.isLoading ? (
                <PageState title="正在加载同步日志" detail="同步任务运行中会持续刷新最近日志。" />
              ) : syncTaskLogsQuery.isError ? (
                <PageState title="同步日志加载失败" detail={syncTaskLogsQuery.error instanceof Error ? syncTaskLogsQuery.error.message : 'unknown error'} />
              ) : !(syncTaskLogsQuery.data?.items?.length) ? (
                <PageState title="暂无同步日志" detail="同步任务开始后，这里会显示最近输出。" />
              ) : (
                <div className="workflow-log-list">
                  {syncTaskLogsQuery.data.items.slice(0, 12).map((item) => (
                    <div key={`${item.log_id}-${item.created_at}`} className="workflow-log-entry">
                      <div className="record-item-head">
                        <strong>{item.run_status ?? item.log_level ?? 'log'}</strong>
                        <span className="inline-meta">{formatTime(item.created_at)}</span>
                      </div>
                      <p>{item.run_message ?? item.run_content ?? '无日志内容'}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}