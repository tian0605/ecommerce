import { Fragment, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  createFullWorkflowListingTask,
  fetchRecentFullWorkflowListingTasks,
  fetchTask,
  fetchTaskLogs,
  precheckFullWorkflowListing,
  retryFullWorkflowListingTask,
} from '../api';
import { WorkspaceSidebar } from '../components/WorkspaceSidebar';
import type { TaskDetailView, WorkflowPrecheckCheck } from '../types';

const WORKFLOW_STEPS = [
  { id: 1, title: '步骤1 采集并认领' },
  { id: 2, title: '步骤2 提取采集箱商品' },
  { id: 3, title: '步骤3 获取物流重量尺寸' },
  { id: 4, title: '步骤4 合并并落库' },
  { id: 5, title: '步骤5 优化标题描述' },
  { id: 6, title: '步骤6 回写妙手ERP' },
];

const RECENT_TASK_PAGE_SIZE = 10;

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

function normalizeUrls(primaryUrl: string, batchUrls: string) {
  const items = [primaryUrl, ...batchUrls.split('\n')]
    .map((item) => item.trim())
    .filter(Boolean);
  return Array.from(new Set(items));
}

function parseCurrentStepIndex(task?: TaskDetailView) {
  const currentStep = task?.progress_checkpoint?.current_step ?? '';
  const match = currentStep.match(/步骤(\d+)/);
  return match ? Number(match[1]) : null;
}

function getStepStatus(stepId: number, task?: TaskDetailView) {
  const execState = (task?.exec_state ?? '').toLowerCase();
  const currentIndex = parseCurrentStepIndex(task);
  if (execState === 'end') {
    return 'passed';
  }
  if (execState === 'error_fix_pending' || execState === 'normal_crash' || execState === 'requires_manual') {
    if (currentIndex == null) {
      return 'failed';
    }
    if (stepId < currentIndex) return 'passed';
    if (stepId === currentIndex) return 'failed';
    return 'waiting';
  }
  if (execState === 'processing' || execState === 'new') {
    if (currentIndex == null) {
      return stepId === 1 ? 'active' : 'waiting';
    }
    if (stepId < currentIndex) return 'passed';
    if (stepId === currentIndex) return 'active';
  }
  return 'waiting';
}

function checkTone(status: WorkflowPrecheckCheck['status']) {
  if (status === 'passed') return 'success';
  if (status === 'warning') return 'warning';
  return 'danger';
}

function classifyWorkflowError(task?: TaskDetailView, logTail?: string[]) {
  const errorText = [
    task?.last_error,
    task?.stage_result,
    task?.progress_checkpoint?.current_step,
    ...(logTail ?? []).slice(0, 10),
  ].join(' ').toLowerCase();

  if (!errorText.trim()) {
    return { label: '暂无错误分类', detail: '任务尚未失败，或当前还没有足够的错误上下文。', tone: 'warning' };
  }
  if (errorText.includes('cookie')) {
    return { label: 'Cookie 失效', detail: '妙手 ERP 登录态可能已过期，建议先刷新 Cookies 后再重试。', tone: 'danger' };
  }
  if (errorText.includes('ssh') || errorText.includes('隧道') || errorText.includes('8080')) {
    return { label: '本地服务/SSH 隧道异常', detail: '本地1688服务或 SSH 隧道不可用，建议先恢复 8080 端口可用性。', tone: 'danger' };
  }
  if (errorText.includes('llm') || errorText.includes('优化') || errorText.includes('timeout')) {
    return { label: '优化阶段超时', detail: '标题描述优化阶段可能超时，建议检查 LLM API 或以轻量模式重试。', tone: 'warning' };
  }
  if (errorText.includes('selector') || errorText.includes('playwright') || errorText.includes('不可见') || errorText.includes('无法点击')) {
    return { label: '浏览器自动化失败', detail: '浏览器元素定位或交互失败，优先查看截图和日志尾部定位页面变化。', tone: 'danger' };
  }
  if (errorText.includes('数据库') || errorText.includes('postgres')) {
    return { label: '数据库异常', detail: '落库阶段可能失败，建议检查数据库连接、连接池和 products/product_skus 写入状态。', tone: 'danger' };
  }
  return { label: '未分类异常', detail: '建议结合日志尾部和截图继续排查，必要时直接重试当前批次。', tone: 'warning' };
}

export function FullWorkflowListingPage() {
  const [primaryUrl, setPrimaryUrl] = useState('');
  const [batchUrls, setBatchUrls] = useState('');
  const [lightweight, setLightweight] = useState(false);
  const [publish, setPublish] = useState(true);
  const [displayName, setDisplayName] = useState('');
  const [expectedDuration, setExpectedDuration] = useState('60');
  const [priority, setPriority] = useState('P1');
  const [note, setNote] = useState('');
  const [selectedTaskName, setSelectedTaskName] = useState<string | null>(null);
  const [recentTaskPage, setRecentTaskPage] = useState(1);
  const [recentTaskKeyword, setRecentTaskKeyword] = useState('');
  const [recentTaskExecState, setRecentTaskExecState] = useState('');
  const [recentTaskPriority, setRecentTaskPriority] = useState('');
  const [recentTaskMode, setRecentTaskMode] = useState('');
  const [recentTaskPublish, setRecentTaskPublish] = useState('');

  const normalizedUrls = useMemo(() => normalizeUrls(primaryUrl, batchUrls), [primaryUrl, batchUrls]);

  const precheckMutation = useMutation({
    mutationFn: () => precheckFullWorkflowListing({
      primary_url: primaryUrl.trim() || undefined,
      urls: normalizedUrls,
      lightweight,
      publish,
      source: 'ops-web',
    }),
  });

  const launchMutation = useMutation({
    mutationFn: () => createFullWorkflowListingTask({
      urls: normalizedUrls,
      lightweight,
      publish,
      display_name: displayName.trim() || undefined,
      expected_duration: Number(expectedDuration) || undefined,
      priority,
      note: note.trim() || undefined,
      source: 'ops-web',
    }),
    onSuccess: (response) => {
      setSelectedTaskName(response.task.task_name);
    },
  });

  const retryMutation = useMutation({
    mutationFn: (taskName: string) => retryFullWorkflowListingTask(taskName),
    onSuccess: (response) => {
      setSelectedTaskName(response.task.task_name);
    },
  });

  const recentTasksQuery = useQuery({
    queryKey: ['workflow-full-listing-recent', recentTaskPage, recentTaskKeyword, recentTaskExecState, recentTaskPriority, recentTaskMode, recentTaskPublish],
    queryFn: () => fetchRecentFullWorkflowListingTasks({
      page: recentTaskPage,
      pageSize: RECENT_TASK_PAGE_SIZE,
      keyword: recentTaskKeyword,
      execState: recentTaskExecState || undefined,
      priority: recentTaskPriority || undefined,
      lightweight: recentTaskMode === '' ? undefined : recentTaskMode === 'lightweight',
      publish: recentTaskPublish === '' ? undefined : recentTaskPublish === 'publish',
    }),
    refetchInterval: 15000,
  });

  useEffect(() => {
    if (!selectedTaskName && recentTasksQuery.data?.items?.length) {
      setSelectedTaskName(recentTasksQuery.data.items[0].task_name);
    }
  }, [recentTasksQuery.data, selectedTaskName]);

  const taskDetailQuery = useQuery({
    queryKey: ['workflow-full-listing-task', selectedTaskName],
    queryFn: () => fetchTask(selectedTaskName as string),
    enabled: selectedTaskName != null,
    refetchInterval: (query) => {
      const data = query.state.data as TaskDetailView | undefined;
      const execState = (data?.exec_state ?? '').toLowerCase();
      return execState === 'new' || execState === 'processing' ? 5000 : false;
    },
  });

  const taskLogsQuery = useQuery({
    queryKey: ['workflow-full-listing-logs', selectedTaskName],
    queryFn: () => fetchTaskLogs(selectedTaskName as string, 80),
    enabled: selectedTaskName != null,
    refetchInterval: () => {
      const execState = (taskDetailQuery.data?.exec_state ?? '').toLowerCase();
      return execState === 'new' || execState === 'processing' ? 8000 : false;
    },
  });

  useEffect(() => {
    precheckMutation.reset();
  }, [primaryUrl, batchUrls, lightweight, publish]);

  const task = taskDetailQuery.data;
  const taskCheckpoint = task?.progress_checkpoint;
  const screenshotPath = taskCheckpoint?.output_data?.screenshot_path;
  const screenshotUrl = taskCheckpoint?.output_data?.cos_url;
  const precheck = precheckMutation.data;
  const logTail = taskLogsQuery.data?.items?.map((item) => item.run_message ?? item.run_content ?? '').filter(Boolean) ?? [];
  const errorCategory = classifyWorkflowError(task, logTail);

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Auto Listing</span>
          <h1>完整工作流上架</h1>
          <p>从 1688 链接发起完整采集、提取、物流、落库、优化与回写流程，执行统一走后台任务。</p>
        </div>

        <div className="agent-list-card">
          <div className="section-head compact">
            <h2>当前任务</h2>
            <span>{task?.task_name ?? '未选择'}</span>
          </div>
          <div className="filter-stack">
            <div className="record-item static auth-inline-card">
              <strong>执行状态</strong>
              <p>{task?.exec_state ?? 'idle'} · {taskCheckpoint?.current_step ?? '等待创建任务'}</p>
            </div>
            <div className="record-item static auth-inline-card">
              <strong>最近更新时间</strong>
              <p>{formatTime(task?.updated_at)}</p>
            </div>
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Workflow Runner</span>
            <h2>完整工作流上架控制台</h2>
            <p>首版提供前置检查、任务创建、步骤时间线、日志跟踪和最近任务历史，浏览器自动化仍由后端任务执行器处理。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">workflow-runner</span>
            <span className="status-pill warning">full flow</span>
            <span className="status-pill success">background task</span>
          </div>
        </section>

        <section className="workflow-grid-top">
          <div className="table-card workflow-panel">
            <div className="section-head">
              <h3>发起流程</h3>
              <span>{normalizedUrls.length} URL</span>
            </div>
            <div className="form-grid">
              <label className="form-field form-field-full">
                <span>单条1688链接</span>
                <input className="filter-input" value={primaryUrl} onChange={(event) => setPrimaryUrl(event.target.value)} placeholder="https://detail.1688.com/offer/1027205078815.html" />
              </label>
              <label className="form-field form-field-full">
                <span>批量链接</span>
                <textarea className="form-textarea" rows={6} value={batchUrls} onChange={(event) => setBatchUrls(event.target.value)} placeholder="每行一条1688链接" />
              </label>
              <label className="form-field">
                <span>流程模式</span>
                <select className="filter-select" value={lightweight ? 'lightweight' : 'full'} onChange={(event) => setLightweight(event.target.value === 'lightweight')}>
                  <option value="full">完整流程</option>
                  <option value="lightweight">轻量流程</option>
                </select>
              </label>
              <label className="form-field">
                <span>发布开关</span>
                <select className="filter-select" value={publish ? 'publish' : 'nopublish'} onChange={(event) => setPublish(event.target.value === 'publish')}>
                  <option value="publish">发布到妙手ERP</option>
                  <option value="nopublish">仅执行到优化前</option>
                </select>
              </label>
              <label className="form-field">
                <span>优先级</span>
                <select className="filter-select" value={priority} onChange={(event) => setPriority(event.target.value)}>
                  <option value="P0">P0</option>
                  <option value="P1">P1</option>
                  <option value="P2">P2</option>
                </select>
              </label>
              <label className="form-field">
                <span>预计时长(分钟)</span>
                <input className="filter-input" value={expectedDuration} onChange={(event) => setExpectedDuration(event.target.value)} placeholder="60" />
              </label>
              <label className="form-field form-field-full">
                <span>任务显示名</span>
                <input className="filter-input" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="可选，默认按任务类型自动生成" />
              </label>
              <label className="form-field form-field-full">
                <span>备注</span>
                <textarea className="form-textarea" rows={3} value={note} onChange={(event) => setNote(event.target.value)} placeholder="记录本次批次的业务说明" />
              </label>
            </div>
            <div className="form-actions workflow-actions">
              <button className="ghost-button" disabled={normalizedUrls.length === 0 || precheckMutation.isPending} onClick={() => precheckMutation.mutate()}>
                {precheckMutation.isPending ? '检查中...' : '预检查'}
              </button>
              <button className="ghost-button" disabled={normalizedUrls.length === 0 || launchMutation.isPending} onClick={() => launchMutation.mutate()}>
                {launchMutation.isPending ? '创建中...' : '创建任务并执行'}
              </button>
              <button className="ghost-button" onClick={() => {
                setPrimaryUrl('');
                setBatchUrls('');
                setDisplayName('');
                setExpectedDuration('60');
                setPriority('P1');
                setNote('');
                setLightweight(false);
                setPublish(true);
              }}>
                清空
              </button>
              <span className="inline-meta">
                {launchMutation.error instanceof Error
                  ? launchMutation.error.message
                  : precheckMutation.error instanceof Error
                    ? precheckMutation.error.message
                    : `当前已归一化 ${normalizedUrls.length} 条链接`}
              </span>
            </div>
          </div>

          <div className="table-card workflow-panel">
            <div className="section-head">
              <h3>前置条件检查</h3>
              <span>{precheck?.status ?? '未执行'}</span>
            </div>
            {!precheck ? (
              <PageState title="尚未执行预检查" detail="创建任务前建议先检查 Cookies、SSH 隧道、本地1688服务、数据库和 LLM 配置。" />
            ) : (
              <div className="workflow-check-list">
                {precheck.checks.map((item) => (
                  <div key={item.key} className="workflow-check-item">
                    <div className="record-item-head">
                      <strong>{item.label}</strong>
                      <span className={`status-pill ${checkTone(item.status)}`}>{item.status}</span>
                    </div>
                    <p>{item.detail}</p>
                    <div className="inline-meta">{item.observed_value ?? item.hint ?? '无附加信息'}</div>
                  </div>
                ))}
                <div className="record-item static">
                  <strong>{precheck.summary}</strong>
                  <p>检查时间：{formatTime(precheck.checked_at)} · {precheck.can_proceed ? '可继续创建任务' : '存在阻塞项'}</p>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="workflow-grid-mid">
          <div className="table-card workflow-panel">
            <div className="section-head">
              <h3>执行时间线</h3>
              <span>{taskCheckpoint?.current_step ?? '等待执行'}</span>
            </div>
            {!task ? (
              <PageState title="暂无任务时间线" detail="创建任务后，这里会持续展示 6 个步骤的实时状态。" />
            ) : (
              <div className="workflow-timeline">
                {WORKFLOW_STEPS.map((step) => {
                  const status = getStepStatus(step.id, task);
                  return (
                    <div key={step.id} className={`workflow-step-card ${status}`}>
                      <div className="record-item-head">
                        <strong>{step.title}</strong>
                        <span className={`status-pill ${status === 'passed' ? 'success' : status === 'active' ? 'warning' : status === 'failed' ? 'danger' : ''}`}>{status}</span>
                      </div>
                      <p>{status === 'active' ? taskCheckpoint?.next_action ?? '执行中' : status === 'passed' ? '已完成' : status === 'failed' ? task?.last_error ?? '执行失败' : '等待执行'}</p>
                      <div className="inline-meta">最近刷新：{formatTime(task.updated_at)}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="workflow-side-column">
            <div className="table-card workflow-panel">
              <div className="section-head">
                <h3>任务摘要</h3>
                <span>{task?.task_name ?? '未选择'}</span>
              </div>
              {!task ? (
                <PageState title="暂无任务摘要" detail="从最近任务中选择，或创建新的完整工作流任务。" />
              ) : (
                <div className="panel-column">
                  <div className="key-value-grid">
                    <div><span className="metric-label">执行状态</span><strong>{task.exec_state ?? 'N/A'}</strong></div>
                    <div><span className="metric-label">阶段状态</span><strong>{task.stage_status ?? 'N/A'}</strong></div>
                    <div><span className="metric-label">当前阶段</span><strong>{task.current_stage ?? 'N/A'}</strong></div>
                    <div><span className="metric-label">下一动作</span><strong>{taskCheckpoint?.next_action ?? 'N/A'}</strong></div>
                    <div><span className="metric-label">商品数量</span><strong>{taskCheckpoint?.product_count ?? taskCheckpoint?.output_data?.product_count ?? 0}</strong></div>
                    <div><span className="metric-label">最近更新</span><strong>{formatTime(task.updated_at)}</strong></div>
                  </div>
                  <div className="record-item static">
                    <strong>当前链接</strong>
                    <p>{taskCheckpoint?.url ?? taskCheckpoint?.output_data?.url ?? 'N/A'}</p>
                  </div>
                  <div className="record-item static">
                    <strong>任务结果</strong>
                    <p>{task.stage_result ?? task.last_error ?? '等待结果'}</p>
                  </div>
                  <div className="record-item static">
                    <strong>失败分类</strong>
                    <p>{errorCategory.label} · {errorCategory.detail}</p>
                  </div>
                  <div className="form-actions compact-actions">
                    <button className="ghost-button" disabled={!task?.task_name || retryMutation.isPending} onClick={() => retryMutation.mutate(task.task_name)}>
                      {retryMutation.isPending ? '重试中...' : '一键重试'}
                    </button>
                    <span className="inline-meta">{retryMutation.error instanceof Error ? retryMutation.error.message : '基于当前任务参数创建新的重试任务'}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="table-card workflow-panel">
              <div className="section-head">
                <h3>错误截图</h3>
                <span>{screenshotUrl || screenshotPath ? 'available' : 'none'}</span>
              </div>
              {!screenshotUrl && !screenshotPath ? (
                <PageState title="暂无错误截图" detail="如果 workflow-runner 捕获到浏览器相关错误，这里会展示本地路径或 COS 链接。" />
              ) : (
                <div className="panel-column">
                  {screenshotUrl ? (
                    <img className="workflow-screenshot-preview" src={screenshotUrl} alt="workflow error screenshot" />
                  ) : null}
                  {screenshotUrl ? (
                    <a className="workflow-link" href={screenshotUrl} target="_blank" rel="noreferrer">打开 COS 截图</a>
                  ) : null}
                  {screenshotPath ? (
                    <div className="record-item static">
                      <strong>本地路径</strong>
                      <p>{screenshotPath}</p>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="workflow-grid-bottom">
          <div className="table-card workflow-panel">
            <div className="section-head">
              <h3>日志尾部</h3>
              <span>{taskLogsQuery.data?.items?.length ?? 0} lines</span>
            </div>
            {taskLogsQuery.isLoading ? (
              <PageState title="正在加载日志" detail="任务运行中会持续刷新最近日志。" />
            ) : taskLogsQuery.isError ? (
              <PageState title="日志加载失败" detail={taskLogsQuery.error instanceof Error ? taskLogsQuery.error.message : 'unknown error'} />
            ) : !(taskLogsQuery.data?.items?.length) ? (
              <PageState title="暂无日志" detail="任务开始运行后，这里会展示最近输出内容。" />
            ) : (
              <div className="workflow-log-list">
                {taskLogsQuery.data.items.slice(0, 20).map((item) => (
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

          <div className="table-card workflow-panel">
            <div className="section-head">
              <h3>最近任务</h3>
              <span>{recentTasksQuery.data?.total ?? 0}</span>
            </div>
            {recentTasksQuery.isLoading ? (
              <PageState title="正在加载最近任务" detail="按 AUTO-LISTING 前缀筛选最近的完整工作流任务。" />
            ) : recentTasksQuery.isError ? (
              <PageState title="最近任务加载失败" detail={recentTasksQuery.error instanceof Error ? recentTasksQuery.error.message : 'unknown error'} />
            ) : (
              <div className="panel-column">
                <div className="filters-panel task-history-filters">
                  <input className="filter-input" value={recentTaskKeyword} onChange={(event) => { setRecentTaskKeyword(event.target.value); setRecentTaskPage(1); }} placeholder="搜索任务名 / 链接 / 步骤" />
                  <select className="filter-select" value={recentTaskExecState} onChange={(event) => { setRecentTaskExecState(event.target.value); setRecentTaskPage(1); }}>
                    <option value="">全部状态</option>
                    <option value="new">new</option>
                    <option value="processing">processing</option>
                    <option value="end">end</option>
                    <option value="error_fix_pending">error_fix_pending</option>
                    <option value="normal_crash">normal_crash</option>
                    <option value="requires_manual">requires_manual</option>
                  </select>
                  <select className="filter-select" value={recentTaskPriority} onChange={(event) => { setRecentTaskPriority(event.target.value); setRecentTaskPage(1); }}>
                    <option value="">全部优先级</option>
                    <option value="P0">P0</option>
                    <option value="P1">P1</option>
                    <option value="P2">P2</option>
                  </select>
                  <select className="filter-select" value={recentTaskMode} onChange={(event) => { setRecentTaskMode(event.target.value); setRecentTaskPage(1); }}>
                    <option value="">全部模式</option>
                    <option value="full">完整流程</option>
                    <option value="lightweight">轻量流程</option>
                  </select>
                  <select className="filter-select" value={recentTaskPublish} onChange={(event) => { setRecentTaskPublish(event.target.value); setRecentTaskPage(1); }}>
                    <option value="">全部发布策略</option>
                    <option value="publish">发布</option>
                    <option value="nopublish">不发布</option>
                  </select>
                </div>

                <div className="record-list compact-list">
                  {(recentTasksQuery.data?.items ?? []).map((item) => (
                    <button key={item.task_name} className={`record-item ${selectedTaskName === item.task_name ? 'active' : ''}`} onClick={() => setSelectedTaskName(item.task_name)}>
                      <div className="record-item-head">
                        <strong>{item.display_name ?? item.task_name}</strong>
                        <span className={`status-pill ${item.exec_state === 'end' ? 'success' : item.exec_state === 'processing' || item.exec_state === 'new' ? 'warning' : 'danger'}`}>{item.exec_state ?? 'unknown'}</span>
                      </div>
                      <p>{item.current_step ?? item.current_stage ?? '等待执行'}</p>
                      <div className="inline-meta">{item.product_count ?? 0} 条 · {item.publish === false ? '不发布' : '发布'} · {item.priority ?? 'P1'} · {formatTime(item.updated_at)}</div>
                    </button>
                  ))}
                </div>

                <PaginationControls
                  page={recentTasksQuery.data?.page ?? recentTaskPage}
                  hasMore={recentTasksQuery.data?.has_more ?? false}
                  total={recentTasksQuery.data?.total ?? 0}
                  pageSize={recentTasksQuery.data?.page_size ?? RECENT_TASK_PAGE_SIZE}
                  onPrev={() => setRecentTaskPage((current) => Math.max(1, current - 1))}
                  onNext={() => { if (recentTasksQuery.data?.has_more) setRecentTaskPage((current) => current + 1); }}
                  onSelectPage={(value) => setRecentTaskPage(value)}
                />
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}