import { Fragment, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  createProfitSyncTask,
  fetchProfitAnalysisItems,
  fetchProfitAnalysisSummary,
  fetchRecentProfitSyncTasks,
  fetchTask,
  fetchTaskLogs,
} from '../api';
import { WorkspaceSidebar } from '../components/WorkspaceSidebar';
import type { TaskDetailView } from '../types';

const PROFIT_ITEMS_PAGE_SIZE = 20;
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

function formatPercent(value?: number | null) {
  if (value == null) return 'N/A';
  return `${(value * 100).toFixed(2)}%`;
}

function resolveSiteCurrency(site?: string | null, currency?: string | null) {
  const normalizedCurrency = String(currency || '').trim().toUpperCase();
  if (normalizedCurrency) return normalizedCurrency;
  const normalizedSite = String(site || '').trim().toUpperCase();
  if (normalizedSite === 'PH' || normalizedSite === 'SHOPEE_PH') return 'PHP';
  return 'TWD';
}

function formatLocalSuggestedPrice(item: {
  site?: string | null;
  currency?: string | null;
  suggested_price_local?: number | null;
  suggested_price_twd?: number | null;
}) {
  const value = item.suggested_price_local ?? item.suggested_price_twd;
  if (value == null) return 'N/A';
  return `${value} ${resolveSiteCurrency(item.site, item.currency)}`;
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
            <button
              className={`ghost-button page-number-button ${pageNumber === props.page ? 'active' : ''}`}
              onClick={() => props.onSelectPage(pageNumber)}
              disabled={pageNumber === props.page}
            >
              {pageNumber}
            </button>
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

export function ProfitAnalysisPage() {
  const [keyword, setKeyword] = useState('');
  const [site, setSite] = useState('TW');
  const [profitRateMin, setProfitRateMin] = useState('');
  const [profitRateMax, setProfitRateMax] = useState('');
  const [page, setPage] = useState(1);
  const [selectedProfitRows, setSelectedProfitRows] = useState<Record<number, string>>({});
  const [syncIdsText, setSyncIdsText] = useState('');
  const [targetProfitRate, setTargetProfitRate] = useState('0.20');
  const [syncPriority, setSyncPriority] = useState('P1');
  const [syncNote, setSyncNote] = useState('');
  const [selectedSyncTaskName, setSelectedSyncTaskName] = useState<string | null>(null);
  const [syncTaskPage, setSyncTaskPage] = useState(1);
  const [syncTaskKeyword, setSyncTaskKeyword] = useState('');
  const [syncTaskExecState, setSyncTaskExecState] = useState('');
  const [syncTaskPriority, setSyncTaskPriority] = useState('');

  const normalizedSyncIds = useMemo(() => normalizeIds(syncIdsText), [syncIdsText]);
  const selectedAlibabaIds = useMemo(
    () => Array.from(new Set(Object.values(selectedProfitRows).filter(Boolean))),
    [selectedProfitRows],
  );

  const summaryQuery = useQuery({
    queryKey: ['profit-analysis-summary', site],
    queryFn: () => fetchProfitAnalysisSummary({ site }),
    refetchInterval: 30000,
  });

  const itemsQuery = useQuery({
    queryKey: ['profit-analysis-items', page, keyword, site, profitRateMin, profitRateMax],
    queryFn: () => fetchProfitAnalysisItems({
      page,
      pageSize: PROFIT_ITEMS_PAGE_SIZE,
      keyword,
      site,
      profitRateMin: profitRateMin ? Number(profitRateMin) : undefined,
      profitRateMax: profitRateMax ? Number(profitRateMax) : undefined,
    }),
    refetchInterval: 30000,
  });

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

  const currentPageSelectableIds = useMemo(
    () => (itemsQuery.data?.items ?? []).map((item) => ({ rowId: item.id, alibabaId: item.alibaba_product_id ?? '' })).filter((item) => item.alibabaId),
    [itemsQuery.data],
  );
  const allCurrentPageSelected = currentPageSelectableIds.length > 0
    && currentPageSelectableIds.every((item) => selectedProfitRows[item.rowId] === item.alibabaId);

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

  function toggleProfitRow(rowId: number, alibabaId?: string | null) {
    if (!alibabaId) {
      return;
    }
    setSelectedProfitRows((current) => {
      const next = { ...current };
      if (next[rowId]) {
        delete next[rowId];
      } else {
        next[rowId] = alibabaId;
      }
      return next;
    });
  }

  function toggleCurrentPageRows() {
    setSelectedProfitRows((current) => {
      const next = { ...current };
      if (allCurrentPageSelected) {
        currentPageSelectableIds.forEach((item) => {
          delete next[item.rowId];
        });
      } else {
        currentPageSelectableIds.forEach((item) => {
          next[item.rowId] = item.alibabaId;
        });
      }
      return next;
    });
  }

  function fillSyncIdsFromSelection() {
    setSyncIdsText(selectedAlibabaIds.join('\n'));
  }

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Profit Management</span>
          <h1>成本利润管理</h1>
          <p>以本地 product_analysis 数据为主控视图，同时提供飞书同步任务创建、状态跟踪和日志查看。</p>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Profit Analysis</span>
            <h2>成本利润管理首版</h2>
            <p>当前页面同时承载本地利润明细查询和飞书同步管理，利润公式仍以 profit-analyzer 为唯一口径。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">local first</span>
            <span className="status-pill warning">feishu sync</span>
          </div>
        </section>

        <section className="metrics-grid page-metrics-grid profit-metrics-grid">
          <div className="metric-card">
            <span className="metric-label">分析商品数</span>
            <strong className="metric-value" data-accent="blue">{summaryQuery.data?.total_products ?? 0}</strong>
          </div>
          <div className="metric-card">
            <span className="metric-label">分析SKU数</span>
            <strong className="metric-value" data-accent="green">{summaryQuery.data?.total_skus ?? 0}</strong>
          </div>
          <div className="metric-card">
            <span className="metric-label">平均利润率</span>
            <strong className="metric-value" data-accent="amber">{formatPercent(summaryQuery.data?.avg_profit_rate ?? null)}</strong>
          </div>
          <div className="metric-card">
            <span className="metric-label">亏损SKU</span>
            <strong className="metric-value" data-accent="red">{summaryQuery.data?.loss_count ?? 0}</strong>
          </div>
        </section>

        <section className="detail-layout profit-page-layout">
          <div className="table-card list-surface">
            <div className="section-head">
              <h3>利润明细</h3>
              <span>{itemsQuery.data?.total ?? 0}</span>
            </div>
            <div className="filters-panel">
              <input className="filter-input" value={keyword} onChange={(event) => { setKeyword(event.target.value); setPage(1); }} placeholder="搜索标题 / 货源ID / SKU" />
              <select className="filter-select" value={site} onChange={(event) => { setSite(event.target.value); setPage(1); }}>
                <option value="TW">TW</option>
                <option value="PH">PH</option>
              </select>
              <input className="filter-input" value={profitRateMin} onChange={(event) => { setProfitRateMin(event.target.value); setPage(1); }} placeholder="最低利润率，如 0.1" />
              <input className="filter-input" value={profitRateMax} onChange={(event) => { setProfitRateMax(event.target.value); setPage(1); }} placeholder="最高利润率，如 0.3" />
            </div>
            <div className="form-actions compact-actions">
              <button className="ghost-button" onClick={toggleCurrentPageRows} disabled={currentPageSelectableIds.length === 0}>
                {allCurrentPageSelected ? '取消本页全选' : '全选本页'}
              </button>
              <button className="ghost-button" onClick={fillSyncIdsFromSelection} disabled={selectedAlibabaIds.length === 0}>
                按选中明细回填同步 ID
              </button>
              <button className="ghost-button" onClick={() => setSelectedProfitRows({})} disabled={selectedAlibabaIds.length === 0}>
                清空选中
              </button>
              <span className="inline-meta">已选 {selectedAlibabaIds.length} 个商品ID，自动按商品去重</span>
            </div>

            {itemsQuery.isLoading ? (
              <PageState title="正在加载利润明细" detail="从本地 product_analysis 表读取 SKU 级成本利润结果。" />
            ) : itemsQuery.isError ? (
              <PageState title="利润明细加载失败" detail={itemsQuery.error instanceof Error ? itemsQuery.error.message : 'unknown error'} />
            ) : !(itemsQuery.data?.items?.length) ? (
              <PageState title="暂无利润明细" detail="当前筛选条件下没有可展示的利润记录。" />
            ) : (
              <div className="panel-column">
                <div className="record-list profit-record-list">
                  {itemsQuery.data.items.map((item) => {
                    const selected = Boolean(item.alibaba_product_id && selectedProfitRows[item.id]);
                    return (
                      <label key={item.id} className={`record-item static selectable-record ${selected ? 'active' : ''}`}>
                        <div className="record-item-head">
                          <div className="selection-head">
                            <input type="checkbox" checked={selected} onChange={() => toggleProfitRow(item.id, item.alibaba_product_id)} disabled={!item.alibaba_product_id} />
                            <strong>{item.title ?? '未命名商品'}</strong>
                          </div>
                          <span className={`status-pill ${Number(item.profit_rate ?? 0) <= 0 ? 'danger' : Number(item.profit_rate ?? 0) < 0.15 ? 'warning' : 'success'}`}>
                            {formatPercent(item.profit_rate ?? null)}
                          </span>
                        </div>
                        <p>{item.alibaba_product_id ?? 'N/A'} · {item.product_id_new ?? 'N/A'} · {item.sku_name ?? '默认SKU'}</p>
                        <div className="profit-inline-grid">
                          <span>采购价(CNY): {item.purchase_price_cny ?? 'N/A'}</span>
                          <span>总成本(CNY): {item.total_cost_cny ?? 'N/A'}</span>
                          <span>建议售价(站点): {formatLocalSuggestedPrice(item)}</span>
                          <span>预计利润(CNY): {item.estimated_profit_cny ?? 'N/A'}</span>
                        </div>
                        <div className="inline-meta">最近分析：{formatTime(item.updated_at)}</div>
                      </label>
                    );
                  })}
                </div>
                <PaginationControls
                  page={itemsQuery.data.page}
                  hasMore={itemsQuery.data.has_more}
                  total={itemsQuery.data.total}
                  pageSize={itemsQuery.data.page_size}
                  onPrev={() => setPage((current) => Math.max(1, current - 1))}
                  onNext={() => { if (itemsQuery.data.has_more) setPage((current) => current + 1); }}
                  onSelectPage={(value) => setPage(value)}
                />
              </div>
            )}
          </div>

          <div className="panel-column profit-side-column">
            <div className="table-card">
              <div className="section-head">
                <h3>飞书同步管理</h3>
                <span>{normalizedSyncIds.length} IDs</span>
              </div>
              <div className="form-grid">
                <label className="form-field form-field-full">
                  <span>1688商品ID</span>
                  <textarea className="form-textarea" rows={5} value={syncIdsText} onChange={(event) => setSyncIdsText(event.target.value)} placeholder="逗号或换行分隔多个 alibaba_id" />
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
                  <textarea className="form-textarea" rows={3} value={syncNote} onChange={(event) => setSyncNote(event.target.value)} placeholder="同步批次说明" />
                </label>
              </div>
              <div className="form-actions">
                <button className="ghost-button" disabled={normalizedSyncIds.length === 0 || syncMutation.isPending} onClick={() => syncMutation.mutate()}>
                  {syncMutation.isPending ? '创建中...' : '创建同步任务'}
                </button>
                <span className="inline-meta">{syncMutation.error instanceof Error ? syncMutation.error.message : `同步目标为配置中的飞书利润分析表，当前 ${normalizedSyncIds.length} 个 ID`}</span>
              </div>
            </div>

            <div className="table-card">
              <div className="section-head">
                <h3>同步任务摘要</h3>
                <span>{syncTask?.task_name ?? '未选择'}</span>
              </div>
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
                  <div className="record-item static">
                    <strong>任务结果</strong>
                    <p>{syncTask.stage_result ?? syncTask.last_error ?? '等待结果'}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="table-card">
              <div className="section-head">
                <h3>最近同步任务</h3>
                <span>{recentSyncTasksQuery.data?.total ?? 0}</span>
              </div>
              {recentSyncTasksQuery.isLoading ? (
                <PageState title="正在加载同步任务" detail="读取最近的 PROFIT-SYNC 后台任务。" />
              ) : recentSyncTasksQuery.isError ? (
                <PageState title="同步任务加载失败" detail={recentSyncTasksQuery.error instanceof Error ? recentSyncTasksQuery.error.message : 'unknown error'} />
              ) : (
                  <div className="panel-column">
                    <div className="filters-panel task-history-filters">
                      <input className="filter-input" value={syncTaskKeyword} onChange={(event) => { setSyncTaskKeyword(event.target.value); setSyncTaskPage(1); }} placeholder="搜索任务名 / 首个ID / 步骤" />
                      <select className="filter-select" value={syncTaskExecState} onChange={(event) => { setSyncTaskExecState(event.target.value); setSyncTaskPage(1); }}>
                        <option value="">全部状态</option>
                        <option value="new">new</option>
                        <option value="processing">processing</option>
                        <option value="end">end</option>
                        <option value="error_fix_pending">error_fix_pending</option>
                        <option value="normal_crash">normal_crash</option>
                        <option value="requires_manual">requires_manual</option>
                      </select>
                      <select className="filter-select" value={syncTaskPriority} onChange={(event) => { setSyncTaskPriority(event.target.value); setSyncTaskPage(1); }}>
                        <option value="">全部优先级</option>
                        <option value="P0">P0</option>
                        <option value="P1">P1</option>
                        <option value="P2">P2</option>
                      </select>
                    </div>
                    <div className="record-list compact-list">
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

            <div className="table-card">
              <div className="section-head">
                <h3>同步日志</h3>
                <span>{syncTaskLogsQuery.data?.items?.length ?? 0}</span>
              </div>
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