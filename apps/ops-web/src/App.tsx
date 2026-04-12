import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import {
  fetchAgent,
  fetchAgentComponents,
  fetchAgentHeartbeats,
  fetchAgentLogs,
  fetchAgentMetrics,
  fetchAgents,
  fetchAgentTasks,
  fetchOverview,
} from './api';
import { ProductManagementPage } from './pages/ProductManagementPage';
import { ProfitDetailsPage } from './pages/ProfitDetailsPage';
import { ProfitSyncManagementPage } from './pages/ProfitSyncManagementPage';
import { ConfigDebugToolsPage, ContentPromptConfigPage, LogisticsProfitConfigPage, MarketConfigsPage, SiteListingsPage } from './pages/UnifiedConfigPages';
import { SystemConfigsPage } from './pages/SystemConfigsPage';
import { FullWorkflowListingPage } from './pages/FullWorkflowListingPage';
import { WorkspaceSidebar } from './components/WorkspaceSidebar';
import { useAuth } from './auth';
import type { Agent, ComponentSummary, Heartbeat, LogEntry, Task } from './types';

type TabKey = 'tasks' | 'logs' | 'heartbeats' | 'health';

function PaginationControls(props: { page: number; hasMore: boolean; total: number; pageSize: number; onPrev: () => void; onNext: () => void }) {
  const totalPages = Math.max(1, Math.ceil(props.total / props.pageSize));
  return (
    <div className="pagination-bar">
      <button className="ghost-button" onClick={props.onPrev} disabled={props.page <= 1}>上一页</button>
      <span>第 {props.page} / {totalPages} 页</span>
      <button className="ghost-button" onClick={props.onNext} disabled={!props.hasMore}>下一页</button>
    </div>
  );
}

function LoadingState(props: { label: string }) {
  return <div className="state-card">正在加载{props.label}...</div>;
}

function ErrorState(props: { label: string; error: string }) {
  return (
    <div className="state-card error">
      <strong>{props.label}加载失败</strong>
      <p>{props.error}</p>
    </div>
  );
}

function EmptyState(props: { label: string }) {
  return <div className="state-card">当前没有{props.label}。</div>;
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

function humanizeToken(value?: string | null) {
  if (!value) return 'N/A';
  return value.replace(/_/g, ' ');
}

function statusTone(status?: string | null) {
  if (!status) return 'muted';
  const normalized = status.toLowerCase();
  if (normalized.includes('critical') || normalized.includes('failed') || normalized.includes('manual') || normalized.includes('degraded')) return 'danger';
  if (normalized.includes('warning') || normalized.includes('processing') || normalized.includes('busy')) return 'warning';
  if (normalized.includes('ok') || normalized.includes('success') || normalized.includes('completed') || normalized.includes('active')) return 'success';
  return 'muted';
}

function MetricCard(props: { label: string; value: string; accent?: string }) {
  return (
    <div className="metric-card">
      <span className="metric-label">{props.label}</span>
      <strong className="metric-value" data-accent={props.accent ?? 'default'}>
        {props.value}
      </strong>
    </div>
  );
}

function ServiceRow(props: { agent: Agent; active: boolean; onClick: () => void }) {
  return (
    <button className={`agent-row ${props.active ? 'active' : ''}`} onClick={props.onClick}>
      <div className="agent-row-main">
        <strong>{props.agent.name}</strong>
        <span className={`status-pill ${statusTone(props.agent.last_heartbeat_status ?? props.agent.status)}`}>
          {props.agent.last_heartbeat_status ?? props.agent.status}
        </span>
      </div>
      <div className="agent-row-meta">
        <span>{props.agent.code}</span>
        <span>{props.agent.pending_task_count ?? 0} pending</span>
      </div>
    </button>
  );
}

function ComponentPanel(props: { items: ComponentSummary[]; selectedCode: string; onSelect: (code: string) => void }) {
  return (
    <section className="table-card component-panel">
      <div className="section-head">
        <h3>组件视图</h3>
        <span>{props.items.length} components</span>
      </div>
      {props.items.length === 0 ? <EmptyState label="组件数据" /> : (
        <div className="component-grid">
          <button className={`component-card ${props.selectedCode === '' ? 'active' : ''}`} onClick={() => props.onSelect('')}>
            <div className="component-head">
              <strong>全部组件</strong>
              <span className="status-pill success">all</span>
            </div>
            <p>查看该服务下全部任务与日志</p>
          </button>
          {props.items.map((item) => (
            <button key={item.code} className={`component-card ${props.selectedCode === item.code ? 'active' : ''}`} onClick={() => props.onSelect(item.code)}>
              <div className="component-head">
                <strong>{item.name}</strong>
                <span className={`status-pill ${statusTone(item.last_heartbeat_status ?? item.status)}`}>
                  {item.last_heartbeat_status ?? item.status}
                </span>
              </div>
              <p>{item.code}</p>
              <div className="component-metrics">
                <span>{item.pending_task_count ?? 0} pending</span>
                <span>{item.processing_task_count ?? 0} processing</span>
                <span>{item.failed_24h_count ?? 0} failed/24h</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function TaskTable(props: { tasks: Task[]; page: number; hasMore: boolean; total: number; onPrev: () => void; onNext: () => void }) {
  return (
    <div className="table-card">
      <div className="section-head">
        <h3>任务列表</h3>
        <span>{props.total} items</span>
      </div>
      {props.tasks.length === 0 ? <EmptyState label="任务" /> : (
        <>
          <div className="table-grid">
            {props.tasks.map((task) => (
              <div key={task.task_name} className="table-row">
                <div>
                  <strong>{task.display_name ?? task.task_name}</strong>
                  <p>{task.task_name}</p>
                  <p>{task.component_name ?? 'Unknown component'}</p>
                </div>
                <div>
                  <div className="status-pill-row">
                    <span className={`status-pill ${statusTone(task.exec_state)}`}>{task.exec_state ?? 'unknown'}</span>
                    <span className={`status-pill ${statusTone(task.stage_status)}`}>{humanizeToken(task.stage_status)}</span>
                  </div>
                  <p>{humanizeToken(task.current_stage)}</p>
                  <p>{task.priority ?? 'N/A'}</p>
                  <p>{task.stage_result ?? '等待阶段结论'}</p>
                </div>
              </div>
            ))}
          </div>
          <PaginationControls page={props.page} hasMore={props.hasMore} total={props.total} pageSize={12} onPrev={props.onPrev} onNext={props.onNext} />
        </>
      )}
    </div>
  );
}

function DistributionPanel(props: { title: string; items: Record<string, number>; updatedAt?: string | null }) {
  const entries = Object.entries(props.items ?? {}).sort((left, right) => right[1] - left[1]);

  return (
    <div className="table-card health-panel">
      <div className="section-head">
        <h3>{props.title}</h3>
        <span>{props.updatedAt ? formatTime(props.updatedAt) : 'current'}</span>
      </div>
      <div className="distribution-list">
        {entries.length === 0 ? (
          <div className="empty-state">当前没有可展示的维度数据。</div>
        ) : entries.map(([name, count]) => (
          <div key={name} className="distribution-row">
            <div>
              <strong>{humanizeToken(name)}</strong>
              <div className="inline-meta">{props.title}</div>
            </div>
            <div className="distribution-stats">
              <span className={`status-pill ${statusTone(name)}`}>{count}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LogList(props: { logs: LogEntry[]; page: number; hasMore: boolean; total: number; onPrev: () => void; onNext: () => void }) {
  return (
    <div className="table-card">
      <div className="section-head">
        <h3>工作日志</h3>
        <span>{props.total} rows</span>
      </div>
      {props.logs.length === 0 ? <EmptyState label="日志" /> : (
        <>
          <div className="timeline-list">
            {props.logs.map((log) => (
              <div key={log.log_id} className="timeline-item">
                <div className="timeline-meta">
                  <span className={`status-pill ${statusTone(log.run_status)}`}>{log.run_status ?? 'unknown'}</span>
                  <span>{formatTime(log.created_at)}</span>
                </div>
                <strong>{log.run_message ?? log.task_name ?? 'No message'}</strong>
                <p>{log.component_name ?? 'Unknown component'} · {log.log_type ?? 'general'} · {log.log_level ?? 'INFO'} · {log.duration_ms ?? 0} ms</p>
              </div>
            ))}
          </div>
          <PaginationControls page={props.page} hasMore={props.hasMore} total={props.total} pageSize={16} onPrev={props.onPrev} onNext={props.onNext} />
        </>
      )}
    </div>
  );
}

function HeartbeatList(props: { items: Heartbeat[]; page: number; hasMore: boolean; total: number; onPrev: () => void; onNext: () => void }) {
  return (
    <div className="table-card">
      <div className="section-head">
        <h3>心跳时间线</h3>
        <span>{props.total} events</span>
      </div>
      {props.items.length === 0 ? <EmptyState label="心跳事件" /> : (
        <>
          <div className="timeline-list">
            {props.items.map((item) => (
              <div key={item.heartbeat_id} className="timeline-item heartbeat-item">
                <div className="timeline-meta">
                  <span className={`status-pill ${statusTone(item.heartbeat_status)}`}>{item.heartbeat_status ?? 'unknown'}</span>
                  <span>{formatTime(item.report_time)}</span>
                </div>
                <strong>{item.summary ?? 'No summary'}</strong>
                <p>pending {item.pending_count ?? 0} · processing {item.processing_count ?? 0} · manual {item.requires_manual_count ?? 0}</p>
              </div>
            ))}
          </div>
          <PaginationControls page={props.page} hasMore={props.hasMore} total={props.total} pageSize={12} onPrev={props.onPrev} onNext={props.onNext} />
        </>
      )}
    </div>
  );
}

function OpsDashboardPage() {
  const { session } = useAuth();
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('tasks');
  const [agentKeyword, setAgentKeyword] = useState('');
  const [componentCode, setComponentCode] = useState('');
  const [taskPage, setTaskPage] = useState(1);
  const [taskExecState, setTaskExecState] = useState('');
  const [taskPriority, setTaskPriority] = useState('');
  const [taskKeyword, setTaskKeyword] = useState('');
  const [logsPage, setLogsPage] = useState(1);
  const [logStatus, setLogStatus] = useState('');
  const [heartbeatsPage, setHeartbeatsPage] = useState(1);
  const [heartbeatStatus, setHeartbeatStatus] = useState('');

  const overviewQuery = useQuery({ queryKey: ['overview'], queryFn: fetchOverview, refetchInterval: 30000 });
  const agentsQuery = useQuery({ queryKey: ['agents', agentKeyword], queryFn: () => fetchAgents({ page: 1, pageSize: 50, keyword: agentKeyword }), refetchInterval: 30000 });

  const agents = agentsQuery.data?.items ?? [];

  const activeAgentId = useMemo(() => {
    if (selectedAgentId) return selectedAgentId;
    return agents[0]?.id ?? null;
  }, [agents, selectedAgentId]);

  const selectAgent = (agentId: number) => {
    setSelectedAgentId(agentId);
    setComponentCode('');
    setTaskPage(1);
    setLogsPage(1);
    setHeartbeatsPage(1);
  };

  const agentQuery = useQuery({ queryKey: ['agent', activeAgentId], queryFn: () => fetchAgent(activeAgentId as number), enabled: !!activeAgentId });
  const componentsQuery = useQuery({ queryKey: ['components', activeAgentId], queryFn: () => fetchAgentComponents(activeAgentId as number), enabled: !!activeAgentId, refetchInterval: 30000 });
  const tasksQuery = useQuery({
    queryKey: ['tasks', activeAgentId, taskPage, taskExecState, taskPriority, taskKeyword, componentCode],
    queryFn: () => fetchAgentTasks(activeAgentId as number, { page: taskPage, pageSize: 12, execState: taskExecState, priority: taskPriority, keyword: taskKeyword, componentCode }),
    enabled: !!activeAgentId,
    refetchInterval: 30000,
  });
  const logsQuery = useQuery({
    queryKey: ['logs', activeAgentId, logsPage, logStatus, componentCode],
    queryFn: () => fetchAgentLogs(activeAgentId as number, { page: logsPage, pageSize: 16, runStatus: logStatus, componentCode }),
    enabled: !!activeAgentId,
    refetchInterval: 15000,
  });
  const heartbeatsQuery = useQuery({
    queryKey: ['heartbeats', activeAgentId, heartbeatsPage, heartbeatStatus],
    queryFn: () => fetchAgentHeartbeats(activeAgentId as number, { page: heartbeatsPage, pageSize: 12, status: heartbeatStatus }),
    enabled: !!activeAgentId,
    refetchInterval: 30000,
  });
  const metricsQuery = useQuery({ queryKey: ['metrics', activeAgentId], queryFn: () => fetchAgentMetrics(activeAgentId as number), enabled: !!activeAgentId, refetchInterval: 30000 });

  const activeAgent = agentQuery.data;
  const components = componentsQuery.data?.items ?? [];
  const tasks = tasksQuery.data?.items ?? [];
  const logs = logsQuery.data?.items ?? [];
  const heartbeats = heartbeatsQuery.data?.items ?? [];
  const metrics = metricsQuery.data;
  const selectedComponent = components.find((item) => item.code === componentCode);

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">OpenClaw Agent Ops</span>
          <h1>运行态控制台</h1>
          <p>面向 OpenClaw 服务维度的任务、日志和心跳观测面。当前会话：{session.user ? `${session.user.display_name} / ${session.user.roles.join(', ')}` : '未登录'}</p>
        </div>

        <div className="agent-list-card">
          <div className="section-head compact">
            <h2>Services</h2>
            <span>{agents.length}</span>
          </div>
          <input className="filter-input" placeholder="搜索服务" value={agentKeyword} onChange={(event) => setAgentKeyword(event.target.value)} />
          <div className="agent-list">
            {agents.map((agent) => (
              <ServiceRow key={agent.id} agent={agent} active={agent.id === activeAgentId} onClick={() => selectAgent(agent.id)} />
            ))}
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Dashboard Overview</span>
            <h2>{activeAgent?.name ?? 'Loading service...'}</h2>
            <p>{selectedComponent ? `当前聚焦组件：${selectedComponent.name}` : activeAgent?.description ?? '正在加载服务详情。'}</p>
          </div>
          <div className="hero-status">
            <span className={`status-pill ${statusTone(activeAgent?.status)}`}>{activeAgent?.status ?? 'unknown'}</span>
            <span className={`status-pill ${statusTone(agents.find((agent) => agent.id === activeAgentId)?.last_heartbeat_status)}`}>{agents.find((agent) => agent.id === activeAgentId)?.last_heartbeat_status ?? 'heartbeat: unknown'}</span>
          </div>
        </section>

        <section className="metrics-grid">
          <MetricCard label="Active Services" value={String(overviewQuery.data?.active_agent_count ?? 0)} accent="blue" />
          <MetricCard label="Pending Tasks" value={String(overviewQuery.data?.pending_task_count ?? 0)} accent="amber" />
          <MetricCard label="Manual Queue" value={String(metrics?.manual_queue_count ?? 0)} accent="red" />
          <MetricCard label="Success Rate 24h" value={metrics?.task_success_rate != null ? `${Math.round(metrics.task_success_rate * 100)}%` : 'N/A'} accent="green" />
          <MetricCard label="Heartbeat Critical" value={String(metrics?.heartbeat_critical_count ?? 0)} accent="red" />
          <MetricCard label="Avg Duration" value={metrics?.avg_duration_ms != null ? `${Math.round(metrics.avg_duration_ms)} ms` : 'N/A'} accent="blue" />
          <MetricCard label="Retrospective" value={String(metrics?.retrospective_queue_count ?? overviewQuery.data?.retrospective_task_count ?? 0)} accent="blue" />
          <MetricCard label="Stage Blocked" value={String(metrics?.blocked_stage_count ?? overviewQuery.data?.blocked_stage_count ?? 0)} accent="amber" />
        </section>

        {componentsQuery.isLoading ? <LoadingState label="组件" /> : componentsQuery.isError ? <ErrorState label="组件" error={componentsQuery.error instanceof Error ? componentsQuery.error.message : 'unknown error'} /> : <ComponentPanel items={components} selectedCode={componentCode} onSelect={setComponentCode} />}

        <section className="tabs-bar">
          {[
            ['tasks', '任务'],
            ['logs', '日志'],
            ['heartbeats', '心跳'],
            ['health', '健康'],
          ].map(([key, label]) => (
            <button key={key} className={`tab-button ${activeTab === key ? 'active' : ''}`} onClick={() => setActiveTab(key as TabKey)}>
              {label}
            </button>
          ))}
        </section>

        <section className="filters-panel">
          {(activeTab === 'tasks' || activeTab === 'logs') && components.length > 0 && (
            <select className="filter-select" value={componentCode} onChange={(event) => { setComponentCode(event.target.value); setTaskPage(1); setLogsPage(1); }}>
              <option value="">全部组件</option>
              {components.map((component) => <option key={component.code} value={component.code}>{component.name}</option>)}
            </select>
          )}
          {activeTab === 'tasks' && (
            <>
              <select className="filter-select" value={taskExecState} onChange={(event) => { setTaskExecState(event.target.value); setTaskPage(1); }}>
                <option value="">全部状态</option>
                <option value="new">new</option>
                <option value="processing">processing</option>
                <option value="error_fix_pending">error_fix_pending</option>
                <option value="requires_manual">requires_manual</option>
                <option value="end">end</option>
              </select>
              <select className="filter-select" value={taskPriority} onChange={(event) => { setTaskPriority(event.target.value); setTaskPage(1); }}>
                <option value="">全部优先级</option>
                <option value="P0">P0</option>
                <option value="P1">P1</option>
                <option value="P2">P2</option>
              </select>
              <input className="filter-input" placeholder="搜索任务" value={taskKeyword} onChange={(event) => { setTaskKeyword(event.target.value); setTaskPage(1); }} />
            </>
          )}
          {activeTab === 'logs' && (
            <select className="filter-select" value={logStatus} onChange={(event) => { setLogStatus(event.target.value); setLogsPage(1); }}>
              <option value="">全部日志状态</option>
              <option value="running">running</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
              <option value="skipped">skipped</option>
              <option value="following">following</option>
            </select>
          )}
          {activeTab === 'heartbeats' && (
            <select className="filter-select" value={heartbeatStatus} onChange={(event) => { setHeartbeatStatus(event.target.value); setHeartbeatsPage(1); }}>
              <option value="">全部心跳状态</option>
              <option value="ok">ok</option>
              <option value="warning">warning</option>
              <option value="critical">critical</option>
            </select>
          )}
        </section>

        <section className="content-grid">
          {activeTab === 'tasks' && (
            tasksQuery.isLoading ? <LoadingState label="任务" /> : tasksQuery.isError ? <ErrorState label="任务" error={tasksQuery.error instanceof Error ? tasksQuery.error.message : 'unknown error'} /> : (
              <TaskTable
                tasks={tasks}
                page={tasksQuery.data?.page ?? taskPage}
                hasMore={tasksQuery.data?.has_more ?? false}
                total={tasksQuery.data?.total ?? 0}
                onPrev={() => setTaskPage((value) => Math.max(1, value - 1))}
                onNext={() => setTaskPage((value) => value + 1)}
              />
            )
          )}
          {activeTab === 'logs' && (
            logsQuery.isLoading ? <LoadingState label="日志" /> : logsQuery.isError ? <ErrorState label="日志" error={logsQuery.error instanceof Error ? logsQuery.error.message : 'unknown error'} /> : (
              <LogList
                logs={logs}
                page={logsQuery.data?.page ?? logsPage}
                hasMore={logsQuery.data?.has_more ?? false}
                total={logsQuery.data?.total ?? 0}
                onPrev={() => setLogsPage((value) => Math.max(1, value - 1))}
                onNext={() => setLogsPage((value) => value + 1)}
              />
            )
          )}
          {activeTab === 'heartbeats' && (
            heartbeatsQuery.isLoading ? <LoadingState label="心跳" /> : heartbeatsQuery.isError ? <ErrorState label="心跳" error={heartbeatsQuery.error instanceof Error ? heartbeatsQuery.error.message : 'unknown error'} /> : (
              <HeartbeatList
                items={heartbeats}
                page={heartbeatsQuery.data?.page ?? heartbeatsPage}
                hasMore={heartbeatsQuery.data?.has_more ?? false}
                total={heartbeatsQuery.data?.total ?? 0}
                onPrev={() => setHeartbeatsPage((value) => Math.max(1, value - 1))}
                onNext={() => setHeartbeatsPage((value) => value + 1)}
              />
            )
          )}
          {activeTab === 'health' && (
            <div className="health-stack">
              <div className="table-card health-panel">
                <div className="section-head">
                  <h3>组件健康分布</h3>
                  <span>{metrics?.metric_window ?? '24h'}</span>
                </div>
                <div className="distribution-list">
                  {components.length === 0 ? (
                    <div className="empty-state">当前服务还没有组件明细。</div>
                  ) : (
                    components.map((component) => (
                      <div key={component.code} className="distribution-row">
                        <div>
                          <strong>{component.name}</strong>
                          <div className="inline-meta">{component.code}</div>
                        </div>
                        <div className="distribution-stats">
                          <span className={`status-pill ${statusTone(component.last_heartbeat_status ?? component.status)}`}>{component.last_heartbeat_status ?? component.status}</span>
                          <span>{component.pending_task_count ?? 0} pending</span>
                          <span>{component.failed_24h_count ?? 0} failed/24h</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
              <DistributionPanel title="Current Stage" items={metrics?.stage_distribution ?? overviewQuery.data?.stage_distribution ?? {}} updatedAt={metrics?.metric_timestamp ?? overviewQuery.data?.metric_timestamp} />
              <DistributionPanel title="Stage Status" items={metrics?.stage_status_distribution ?? overviewQuery.data?.stage_status_distribution ?? {}} updatedAt={metrics?.metric_timestamp ?? overviewQuery.data?.metric_timestamp} />
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<OpsDashboardPage />} />
        <Route path="/products" element={<ProductManagementPage />} />
        <Route path="/operations/auto-listing/workflow" element={<FullWorkflowListingPage />} />
        <Route path="/operations/profit/details" element={<ProfitDetailsPage />} />
        <Route path="/operations/profit/feishu-sync" element={<ProfitSyncManagementPage />} />
        <Route path="/operations/configs/markets" element={<MarketConfigsPage />} />
        <Route path="/operations/configs/shipping" element={<LogisticsProfitConfigPage />} />
        <Route path="/operations/configs/content" element={<ContentPromptConfigPage />} />
        <Route path="/operations/configs/prompts" element={<ContentPromptConfigPage />} />
        <Route path="/operations/configs/fees" element={<LogisticsProfitConfigPage />} />
        <Route path="/operations/configs/debug" element={<ConfigDebugToolsPage />} />
        <Route path="/operations/configs/site-listings" element={<SiteListingsPage />} />
        <Route path="/operations/configs/system" element={<SystemConfigsPage />} />
        <Route path="/profit-analysis" element={<Navigate to="/operations/profit/details" replace />} />
        <Route path="/system-configs" element={<Navigate to="/operations/configs/system" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}
