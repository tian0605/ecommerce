import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchSystemConfig, fetchSystemConfigSummary, fetchSystemConfigs, rollbackSystemConfig, updateSystemConfig } from '../api';
import { useAuth } from '../auth';
import { WorkspaceSidebar } from '../components/WorkspaceSidebar';

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

export function SystemConfigsPage() {
  const { session } = useAuth();
  const [category, setCategory] = useState('');
  const [keyword, setKeyword] = useState('');
  const [verifyStatus, setVerifyStatus] = useState('');
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [formState, setFormState] = useState({
    value: '',
    description: '',
    change_reason: '',
  });
  const [saveMessage, setSaveMessage] = useState('');
  const queryClient = useQueryClient();

  const configsQuery = useQuery({
    queryKey: ['system-configs', category, keyword, verifyStatus],
    queryFn: () => fetchSystemConfigs({ page: 1, pageSize: 100, category, keyword, verifyStatus }),
    refetchInterval: 30000,
  });
  const summaryQuery = useQuery({
    queryKey: ['system-config-summary'],
    queryFn: fetchSystemConfigSummary,
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!selectedKey && configsQuery.data?.items?.length) {
      setSelectedKey(configsQuery.data.items[0].config_key);
    }
  }, [configsQuery.data, selectedKey]);

  const configDetailQuery = useQuery({
    queryKey: ['system-config-detail', selectedKey],
    queryFn: () => fetchSystemConfig(selectedKey as string),
    enabled: selectedKey != null,
  });

  const categoryOptions = useMemo(() => {
    const names = new Set(configsQuery.data?.items.map((item) => item.category) ?? []);
    return Array.from(names).sort();
  }, [configsQuery.data]);

  const detail = configDetailQuery.data;
  const mutation = useMutation({
    mutationFn: () => updateSystemConfig(selectedKey as string, {
      environment: detail?.environment ?? 'prod',
      value: formState.value.trim() || undefined,
      description: formState.description,
      change_reason: formState.change_reason.trim() || undefined,
      verify_after_save: true,
    }),
    onSuccess: (response) => {
      setSaveMessage(response.message);
      queryClient.setQueryData(['system-config-detail', selectedKey], response.config);
      queryClient.invalidateQueries({ queryKey: ['system-configs'] });
      queryClient.invalidateQueries({ queryKey: ['system-config-summary'] });
      queryClient.invalidateQueries({ queryKey: ['system-config-detail', selectedKey] });
    },
    onError: (error) => {
      setSaveMessage(error instanceof Error ? error.message : '配置保存失败');
    },
  });
  const rollbackMutation = useMutation({
    mutationFn: (logId: number) => rollbackSystemConfig(selectedKey as string, logId, detail?.environment ?? 'prod'),
    onSuccess: (response) => {
      setSaveMessage(response.message);
      queryClient.setQueryData(['system-config-detail', selectedKey], response.config);
      queryClient.invalidateQueries({ queryKey: ['system-configs'] });
      queryClient.invalidateQueries({ queryKey: ['system-config-summary'] });
      queryClient.invalidateQueries({ queryKey: ['system-config-detail', selectedKey] });
    },
    onError: (error) => {
      setSaveMessage(error instanceof Error ? error.message : '配置回滚失败');
    },
  });

  useEffect(() => {
    if (!detail) {
      return;
    }
    setFormState((prev) => ({
      ...prev,
      value: detail.secret_level === 'masked' ? detail.value_masked ?? '' : '',
      description: detail.description ?? '',
      change_reason: '',
    }));
    setSaveMessage('');
  }, [detail]);

  const validationMessage = useMemo(() => {
    if (!detail) {
      return '';
    }
    if (!session.authenticated) {
      return '请先登录后再保存配置';
    }
    const hasValue = formState.value.trim().length > 0;
    const hasDescriptionChange = formState.description !== (detail.description ?? '');
    if (!hasValue && !hasDescriptionChange) {
      return '至少修改值或说明后再保存';
    }
    if (detail.is_required && !hasValue && (detail.value_masked == null || detail.value_masked === '未配置')) {
      return '当前配置为必填且无值，必须输入新值';
    }
    if (detail.secret_level !== 'masked' && !formState.change_reason.trim()) {
      return '敏感配置必须填写变更原因';
    }
    return '';
  }, [detail, formState, session.authenticated]);

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Phase 1</span>
          <h1>配置中心</h1>
          <p>当前先接入配置只读、掩码展示和状态概览，为第二阶段的保存与验证做准备。</p>
        </div>

        <div className="agent-list-card">
          <div className="section-head compact">
            <h2>配置分类</h2>
            <span>{categoryOptions.length}</span>
          </div>
          <div className="filter-stack">
            <input className="filter-input" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索配置键 / 配置名" />
            <select className="filter-select" value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">全部分类</option>
              {categoryOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <select className="filter-select" value={verifyStatus} onChange={(event) => setVerifyStatus(event.target.value)}>
              <option value="">全部验证状态</option>
              <option value="success">success</option>
              <option value="warning">warning</option>
              <option value="failed">failed</option>
            </select>
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Configuration Center</span>
            <h2>系统配置只读骨架</h2>
            <p>当前已汇总环境文件、模型配置和 cookies 路径等核心配置元数据，敏感值默认只展示掩码，写操作通过服务端 session 与 RBAC 控制。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">masked</span>
            <span className="status-pill warning">readonly</span>
          </div>
        </section>

        <section className="metrics-grid page-metrics-grid">
          <div className="metric-card">
            <span className="metric-label">配置数量</span>
            <strong className="metric-value" data-accent="blue">{summaryQuery.data?.total_configs ?? configsQuery.data?.total ?? 0}</strong>
          </div>
          <div className="metric-card">
            <span className="metric-label">告警配置</span>
            <strong className="metric-value" data-accent="green">{summaryQuery.data?.failed_configs ?? 0}</strong>
          </div>
          <div className="metric-card">
            <span className="metric-label">即将过期</span>
            <strong className="metric-value" data-accent="amber">{summaryQuery.data?.expiring_configs ?? 0}</strong>
          </div>
        </section>

        <section className="detail-layout">
          <div className="table-card list-surface">
            <div className="section-head">
              <h3>配置列表</h3>
              <span>{configsQuery.data?.total ?? 0}</span>
            </div>
            {configsQuery.isLoading ? (
              <PageState title="正在加载配置列表" detail="汇总环境配置与关键凭证元数据。" />
            ) : configsQuery.isError ? (
              <PageState title="配置列表加载失败" detail={configsQuery.error instanceof Error ? configsQuery.error.message : 'unknown error'} />
            ) : (
              <div className="record-list">
                {(configsQuery.data?.items ?? []).map((item) => (
                  <button key={item.config_key} className={`record-item ${selectedKey === item.config_key ? 'active' : ''}`} onClick={() => setSelectedKey(item.config_key)}>
                    <div className="record-item-head">
                      <strong>{item.config_name}</strong>
                      <span className={`status-pill ${item.last_verify_status === 'success' ? 'success' : item.last_verify_status === 'warning' ? 'warning' : 'danger'}`}>
                        {item.last_verify_status ?? 'unknown'}
                      </span>
                    </div>
                    <p>{item.category} · {item.environment}</p>
                    <div className="inline-meta">{item.value_masked ?? '未配置'}</div>
                    <div className="inline-meta">{(item.source_files ?? []).join(', ') || '未标记来源'} </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="table-card list-surface">
            <div className="section-head">
              <h3>配置详情</h3>
              <span>{detail?.config_key ?? '未选择'}</span>
            </div>
            {configDetailQuery.isLoading ? (
              <PageState title="正在加载配置详情" detail="加载掩码值、依赖关系和验证状态。" />
            ) : configDetailQuery.isError ? (
              <PageState title="配置详情加载失败" detail={configDetailQuery.error instanceof Error ? configDetailQuery.error.message : 'unknown error'} />
            ) : !detail ? (
              <PageState title="暂无配置详情" detail="先从左侧选择一项配置。" />
            ) : (
              <div className="panel-column">
                <div className="key-value-grid">
                  <div><span className="metric-label">配置分类</span><strong>{detail.category}</strong></div>
                  <div><span className="metric-label">环境</span><strong>{detail.environment}</strong></div>
                  <div><span className="metric-label">值类型</span><strong>{detail.value_type}</strong></div>
                  <div><span className="metric-label">敏感级别</span><strong>{detail.secret_level}</strong></div>
                  <div><span className="metric-label">配置来源</span><strong>{(detail.source_files ?? []).join(', ') || 'N/A'}</strong></div>
                  <div><span className="metric-label">依赖服务</span><strong>{(detail.dependent_services ?? []).join(', ') || 'N/A'}</strong></div>
                </div>
                <div className="record-item static config-value-card">
                  <strong>当前值</strong>
                  <p className="config-value">{detail.value_masked ?? '未配置'}</p>
                </div>
                <div className="record-item static">
                  <strong>说明</strong>
                  <p>{detail.description ?? '暂无说明'}</p>
                </div>
                <div className="record-item static">
                  <strong>验证状态</strong>
                  <p>{detail.last_verify_status ?? 'unknown'} · {detail.last_verify_message ?? '暂无验证信息'}</p>
                </div>
                <div className="record-item static">
                  <strong>依赖关系</strong>
                  <p>{JSON.stringify(detail.dependency_json ?? {}, null, 2)}</p>
                </div>
                <div className="record-item static">
                  <div className="section-head compact">
                    <h3>保存配置</h3>
                    <span>{mutation.isPending ? 'saving' : 'ready'}</span>
                  </div>
                  <div className="form-grid">
                    <div className="record-item static auth-inline-card">
                      <strong>当前会话</strong>
                      <p>{session.user ? `${session.user.display_name} (${session.user.roles.join(', ')})` : '未登录'}</p>
                    </div>
                    <label className="form-field form-field-full">
                      <span>新值</span>
                      <textarea className="form-textarea" rows={4} value={formState.value} onChange={(event) => setFormState((prev) => ({ ...prev, value: event.target.value }))} placeholder={detail.secret_level === 'masked' ? '输入新的配置值' : '敏感字段不会回填原值，需输入完整新值'} />
                    </label>
                    <label className="form-field form-field-full">
                      <span>说明</span>
                      <textarea className="form-textarea" rows={3} value={formState.description} onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))} />
                    </label>
                    <label className="form-field form-field-full">
                      <span>变更原因</span>
                      <textarea className="form-textarea" rows={3} value={formState.change_reason} onChange={(event) => setFormState((prev) => ({ ...prev, change_reason: event.target.value }))} placeholder="敏感配置必填" />
                    </label>
                  </div>
                  <div className="form-actions">
                    <button className="ghost-button" disabled={Boolean(validationMessage) || mutation.isPending} onClick={() => mutation.mutate()}>
                      {mutation.isPending ? '保存中...' : '保存配置'}
                    </button>
                    <span className="inline-meta">{validationMessage || saveMessage || `${detail.secret_level} 配置按 session RBAC 控制`}</span>
                  </div>
                </div>
                <div className="section-head compact">
                  <h3>最近变更</h3>
                  <span>{detail.recent_changes.length}</span>
                </div>
                <div className="record-list compact-list">
                  {detail.recent_changes.length === 0 ? (
                    <div className="empty-state">第一阶段尚未接入真实配置审计表。</div>
                  ) : (
                    detail.recent_changes.map((change, index) => (
                      <div key={`${change.action_type}-${index}`} className="record-item static">
                        <div className="record-item-head">
                          <strong>{change.action_type}</strong>
                          <span className="inline-meta">{change.created_at ?? 'N/A'}</span>
                        </div>
                        <p>{change.change_reason ?? '无变更原因'}</p>
                        {change.id ? (
                          <button className="ghost-button" disabled={!session.authenticated || rollbackMutation.isPending} onClick={() => rollbackMutation.mutate(change.id as number)}>
                            {rollbackMutation.isPending ? '回滚中...' : '回滚到此版本'}
                          </button>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}