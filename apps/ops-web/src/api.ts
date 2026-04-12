import type {
  Agent,
  AgentMetrics,
  AuthSessionView,
  ComponentSummary,
  DashboardOverview,
  Heartbeat,
  LoginPayload,
  MediaUploadCompleteResponse,
  LogEntry,
  MediaUploadRequestPayload,
  MediaSortPayload,
  MediaUploadTicketResponse,
  OpsConfigMutationResponse,
  MarketConfigDetail,
  MarketConfigListItem,
  PaginatedResponse,
  ProductDetail,
  ProductListItem,
  ProductMutationResponse,
  ProfitAnalysisItem,
  ProfitAnalysisSummary,
  ProfitInitRetryResponse,
  ProfitInitCandidateSummary,
  ProfitInitLaunchResponse,
  ProfitInitRecentTaskItem,
  ProfitSyncLaunchResponse,
  ProfitSyncRecentTaskItem,
  ProductSkuUpdatePayload,
  ProductUpdatePayload,
  ShippingProfileDetail,
  ShippingProfileListItem,
  SiteListingDetail,
  SiteListingListItem,
  SkeletonMutationResponse,
  ContentPolicyDetail,
  ContentPolicyListItem,
  FeeProfileDetail,
  FeeProfileListItem,
  ProfitTrialResponse,
  PromptPreviewResponse,
  PromptProfileDetail,
  PromptProfileListItem,
  SystemConfigDetail,
  SystemConfigListItem,
  SystemConfigMutationResponse,
  SystemConfigSummary,
  SystemConfigUpdatePayload,
  Task,
  TaskDetailView,
  WorkflowLaunchPayload,
  WorkflowLaunchResponse,
  WorkflowPrecheckResponse,
  WorkflowRecentTaskItem,
  WorkflowRetryResponse,
} from './types';

function resolveApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }

  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:8010';
  }

  const { hostname, host, protocol } = window.location;
  if (hostname === '127.0.0.1' || hostname === 'localhost') {
    return 'http://127.0.0.1:8010';
  }

  if (window.location.port === '5174') {
    return `${protocol}//${hostname}:8010`;
  }

  return `${protocol}//${host}/api`;
}

const API_BASE_URL = resolveApiBaseUrl();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...init,
  });
  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    try {
      const payload = await response.json() as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // ignore non-json response body
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function jsonRequest<T>(path: string, method: string, body: unknown) {
  return request<T>(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
}

export function fetchOverview() {
  return request<DashboardOverview>('/dashboard/overview');
}

export function fetchAuthSession() {
  return request<AuthSessionView>('/auth/me');
}

export function loginSession(payload: LoginPayload) {
  return jsonRequest<AuthSessionView>('/auth/login', 'POST', payload);
}

export function logoutSession() {
  return jsonRequest<AuthSessionView>('/auth/logout', 'POST', {});
}

function withQuery(path: string, params: Record<string, string | number | boolean | undefined | null>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export function fetchAgents(params: { page?: number; pageSize?: number; status?: string; type?: string; keyword?: string } = {}) {
  return request<PaginatedResponse<Agent>>(withQuery('/agents', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
    status: params.status,
    type: params.type,
    keyword: params.keyword,
  }));
}

export function fetchAgent(agentId: number) {
  return request<Agent>(`/agents/${agentId}`);
}

export function fetchAgentComponents(agentId: number) {
  return request<{ items: ComponentSummary[] }>(`/agents/${agentId}/components`);
}

export function fetchAgentTasks(
  agentId: number,
  params: { page?: number; pageSize?: number; execState?: string; priority?: string; taskType?: string; keyword?: string; componentCode?: string } = {},
) {
  return request<PaginatedResponse<Task>>(withQuery(`/agents/${agentId}/tasks`, {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 12,
    exec_state: params.execState,
    priority: params.priority,
    task_type: params.taskType,
    keyword: params.keyword,
    component_code: params.componentCode,
  }));
}

export function fetchAgentLogs(
  agentId: number,
  params: { page?: number; pageSize?: number; runStatus?: string; logType?: string; componentCode?: string } = {},
) {
  return request<PaginatedResponse<LogEntry>>(withQuery(`/agents/${agentId}/logs`, {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 16,
    run_status: params.runStatus,
    log_type: params.logType,
    component_code: params.componentCode,
  }));
}

export function fetchAgentHeartbeats(
  agentId: number,
  params: { page?: number; pageSize?: number; status?: string } = {},
) {
  return request<PaginatedResponse<Heartbeat>>(withQuery(`/agents/${agentId}/heartbeats`, {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 12,
    status: params.status,
  }));
}

export function fetchAgentMetrics(agentId: number) {
  return request<AgentMetrics>(`/agents/${agentId}/metrics?window=24h`);
}

export function precheckFullWorkflowListing(payload: {
  primary_url?: string;
  urls: string[];
  lightweight: boolean;
  publish: boolean;
  source?: string;
}) {
  return jsonRequest<WorkflowPrecheckResponse>('/workflow-tasks/full-listing/precheck', 'POST', payload);
}

export function createFullWorkflowListingTask(payload: WorkflowLaunchPayload) {
  return jsonRequest<WorkflowLaunchResponse>('/workflow-tasks/full-listing', 'POST', payload);
}

export function retryFullWorkflowListingTask(taskName: string) {
  return request<WorkflowRetryResponse>(`/workflow-tasks/full-listing/${encodeURIComponent(taskName)}/retry`, {
    method: 'POST',
  });
}

export function fetchRecentFullWorkflowListingTasks(params: {
  page?: number;
  pageSize?: number;
  execState?: string;
  priority?: string;
  lightweight?: boolean;
  publish?: boolean;
  keyword?: string;
} = {}) {
  return request<PaginatedResponse<WorkflowRecentTaskItem>>(withQuery('/workflow-tasks/full-listing/recent', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 20,
    exec_state: params.execState,
    priority: params.priority,
    lightweight: params.lightweight,
    publish: params.publish,
    keyword: params.keyword,
  }));
}

export function fetchTask(taskName: string) {
  return request<TaskDetailView>(`/tasks/${encodeURIComponent(taskName)}`);
}

export function fetchTaskLogs(taskName: string, limit = 200) {
  return request<{ items: LogEntry[] }>(withQuery(`/tasks/${encodeURIComponent(taskName)}/logs`, { limit }));
}

export function fetchProfitAnalysisSummary(params: { site?: string } = {}) {
  return request<ProfitAnalysisSummary>(withQuery('/profit-analysis/summary', {
    site: params.site,
  }));
}

export function fetchProfitInitCandidateSummary(params: { site?: string } = {}) {
  return request<ProfitInitCandidateSummary>(withQuery('/profit-analysis/init/candidates/summary', {
    site: params.site,
  }));
}

export function fetchProfitAnalysisItems(params: {
  page?: number;
  pageSize?: number;
  keyword?: string;
  site?: string;
  profitRateMin?: number;
  profitRateMax?: number;
} = {}) {
  return request<PaginatedResponse<ProfitAnalysisItem>>(withQuery('/profit-analysis/items', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 20,
    keyword: params.keyword,
    site: params.site,
    profit_rate_min: params.profitRateMin,
    profit_rate_max: params.profitRateMax,
  }));
}

export function createProfitSyncTask(payload: {
  alibaba_ids: string[];
  profit_rate: number;
  display_name?: string;
  expected_duration?: number;
  priority?: string;
  note?: string;
  source?: string;
}) {
  return jsonRequest<ProfitSyncLaunchResponse>('/profit-analysis/sync', 'POST', payload);
}

export function createProfitInitTask(payload: {
  scope: 'missing_only' | 'all_products';
  site?: string;
  force_recalculate?: boolean;
  profit_rate?: number;
  batch_size?: number;
  priority?: string;
  note?: string;
  source?: string;
}) {
  return jsonRequest<ProfitInitLaunchResponse>('/profit-analysis/init', 'POST', payload);
}

export function retryProfitInitTask(taskName: string) {
  return request<ProfitInitRetryResponse>(`/profit-analysis/init/${encodeURIComponent(taskName)}/retry`, {
    method: 'POST',
  });
}

export function fetchRecentProfitSyncTasks(params: { page?: number; pageSize?: number; execState?: string; priority?: string; keyword?: string } = {}) {
  return request<PaginatedResponse<ProfitSyncRecentTaskItem>>(withQuery('/profit-analysis/sync/recent', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 20,
    exec_state: params.execState,
    priority: params.priority,
    keyword: params.keyword,
  }));
}

export function fetchRecentProfitInitTasks(params: { page?: number; pageSize?: number; execState?: string; priority?: string; keyword?: string } = {}) {
  return request<PaginatedResponse<ProfitInitRecentTaskItem>>(withQuery('/profit-analysis/init/recent', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 20,
    exec_state: params.execState,
    priority: params.priority,
    keyword: params.keyword,
  }));
}

export function fetchProducts(
  params: {
    page?: number;
    pageSize?: number;
    keyword?: string;
    status?: string;
    quickFilter?: string;
    siteFilter?: string;
    priceMin?: number;
    priceMax?: number;
    inventoryWarningOnly?: boolean;
    listingOnly?: boolean;
  } = {},
) {
  return request<PaginatedResponse<ProductListItem>>(withQuery('/products', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 24,
    keyword: params.keyword,
    status: params.status,
    quick_filter: params.quickFilter,
    site_filter: params.siteFilter,
    price_min: params.priceMin,
    price_max: params.priceMax,
    inventory_warning_only: params.inventoryWarningOnly,
    listing_only: params.listingOnly,
  }));
}

export function fetchProduct(productId: number) {
  return request<ProductDetail>(`/products/${productId}`);
}

export function fetchSystemConfigs(params: { page?: number; pageSize?: number; category?: string; environment?: string; keyword?: string; verifyStatus?: string; isActive?: boolean } = {}) {
  return request<PaginatedResponse<SystemConfigListItem>>(withQuery('/system-configs', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
    category: params.category,
    environment: params.environment,
    keyword: params.keyword,
    verify_status: params.verifyStatus,
    is_active: params.isActive == null ? undefined : String(params.isActive),
  }));
}

export function fetchSystemConfig(configKey: string, environment = 'prod') {
  return request<SystemConfigDetail>(withQuery(`/system-configs/${encodeURIComponent(configKey)}`, { environment }));
}

export function fetchSystemConfigSummary() {
  return request<SystemConfigSummary>('/system-configs/summary');
}

export function fetchMarketConfigs(params: { page?: number; pageSize?: number; keyword?: string; siteCode?: string; isActive?: boolean } = {}) {
  return request<PaginatedResponse<MarketConfigListItem>>(withQuery('/ops-configs/market-configs', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
    keyword: params.keyword,
    site_code: params.siteCode,
    is_active: params.isActive == null ? undefined : String(params.isActive),
  }));
}

export function fetchMarketConfig(marketCode: string) {
  return request<MarketConfigDetail>(`/ops-configs/market-configs/${encodeURIComponent(marketCode)}`);
}

export function updateMarketConfig(marketCode: string, payload: Record<string, unknown>) {
  return jsonRequest<OpsConfigMutationResponse<MarketConfigDetail>>(`/ops-configs/market-configs/${encodeURIComponent(marketCode)}`, 'PUT', payload);
}

export function fetchShippingProfiles(params: { page?: number; pageSize?: number; keyword?: string; siteCode?: string; isActive?: boolean } = {}) {
  return request<PaginatedResponse<ShippingProfileListItem>>(withQuery('/ops-configs/shipping-profiles', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
    keyword: params.keyword,
    site_code: params.siteCode,
    is_active: params.isActive == null ? undefined : String(params.isActive),
  }));
}

export function fetchShippingProfile(shippingProfileCode: string) {
  return request<ShippingProfileDetail>(`/ops-configs/shipping-profiles/${encodeURIComponent(shippingProfileCode)}`);
}

export function updateShippingProfile(shippingProfileCode: string, payload: Record<string, unknown>) {
  return jsonRequest<OpsConfigMutationResponse<ShippingProfileDetail>>(`/ops-configs/shipping-profiles/${encodeURIComponent(shippingProfileCode)}`, 'PUT', payload);
}

export function fetchContentPolicies(params: { page?: number; pageSize?: number; keyword?: string; siteCode?: string; isActive?: boolean } = {}) {
  return request<PaginatedResponse<ContentPolicyListItem>>(withQuery('/ops-configs/content-policies', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
    keyword: params.keyword,
    site_code: params.siteCode,
    is_active: params.isActive == null ? undefined : String(params.isActive),
  }));
}

export function fetchContentPolicy(contentPolicyCode: string) {
  return request<ContentPolicyDetail>(`/ops-configs/content-policies/${encodeURIComponent(contentPolicyCode)}`);
}

export function updateContentPolicy(contentPolicyCode: string, payload: Record<string, unknown>) {
  return jsonRequest<OpsConfigMutationResponse<ContentPolicyDetail>>(`/ops-configs/content-policies/${encodeURIComponent(contentPolicyCode)}`, 'PUT', payload);
}

export function fetchPromptProfiles(params: { page?: number; pageSize?: number; keyword?: string; siteCode?: string; isActive?: boolean } = {}) {
  return request<PaginatedResponse<PromptProfileListItem>>(withQuery('/ops-configs/prompt-profiles', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
    keyword: params.keyword,
    site_code: params.siteCode,
    is_active: params.isActive == null ? undefined : String(params.isActive),
  }));
}

export function fetchPromptProfile(promptProfileCode: string) {
  return request<PromptProfileDetail>(`/ops-configs/prompt-profiles/${encodeURIComponent(promptProfileCode)}`);
}

export function updatePromptProfile(promptProfileCode: string, payload: Record<string, unknown>) {
  return jsonRequest<OpsConfigMutationResponse<PromptProfileDetail>>(`/ops-configs/prompt-profiles/${encodeURIComponent(promptProfileCode)}`, 'PUT', payload);
}

export function fetchFeeProfiles(params: { page?: number; pageSize?: number; keyword?: string; siteCode?: string; isActive?: boolean } = {}) {
  return request<PaginatedResponse<FeeProfileListItem>>(withQuery('/ops-configs/fee-profiles', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
    keyword: params.keyword,
    site_code: params.siteCode,
    is_active: params.isActive == null ? undefined : String(params.isActive),
  }));
}

export function fetchFeeProfile(feeProfileCode: string) {
  return request<FeeProfileDetail>(`/ops-configs/fee-profiles/${encodeURIComponent(feeProfileCode)}`);
}

export function updateFeeProfile(feeProfileCode: string, payload: Record<string, unknown>) {
  return jsonRequest<OpsConfigMutationResponse<FeeProfileDetail>>(`/ops-configs/fee-profiles/${encodeURIComponent(feeProfileCode)}`, 'PUT', payload);
}

export function generatePromptPreview(payload: Record<string, unknown>) {
  return jsonRequest<PromptPreviewResponse>('/ops-configs/prompt-preview', 'POST', payload);
}

export function runProfitTrial(payload: Record<string, unknown>) {
  return jsonRequest<ProfitTrialResponse>('/ops-configs/profit-trial', 'POST', payload);
}

export function fetchOpsSiteListings(params: {
  page?: number;
  pageSize?: number;
  keyword?: string;
  siteCode?: string;
  publishStatus?: string;
  syncStatus?: string;
} = {}) {
  return request<PaginatedResponse<SiteListingListItem>>(withQuery('/ops-configs/site-listings', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 100,
    keyword: params.keyword,
    site_code: params.siteCode,
    publish_status: params.publishStatus,
    sync_status: params.syncStatus,
  }));
}

export function fetchOpsSiteListing(siteListingId: number) {
  return request<SiteListingDetail>(`/ops-configs/site-listings/${siteListingId}`);
}

export function resolveAssetUrl(assetUrl?: string | null) {
  if (!assetUrl) {
    return '';
  }
  if (/^https?:\/\//.test(assetUrl)) {
    return assetUrl;
  }
  if (assetUrl.startsWith('/')) {
    return `${API_BASE_URL}${assetUrl}`;
  }
  return `${API_BASE_URL}/${assetUrl}`;
}

export function updateProduct(productId: number, payload: ProductUpdatePayload) {
  return jsonRequest<ProductMutationResponse>(`/products/${productId}`, 'PATCH', payload);
}

export function updateProductSku(productId: number, skuId: number, payload: ProductSkuUpdatePayload) {
  return jsonRequest<ProductMutationResponse>(`/products/${productId}/skus/${skuId}`, 'PATCH', payload);
}

export function updateSystemConfig(configKey: string, payload: SystemConfigUpdatePayload) {
  return jsonRequest<SystemConfigMutationResponse>(`/system-configs/${encodeURIComponent(configKey)}`, 'PUT', payload);
}

export function createMediaUploadRequest(payload: MediaUploadRequestPayload) {
  return jsonRequest<MediaUploadTicketResponse>('/media-assets/uploads', 'POST', payload);
}

export function uploadMediaFile(uploadToken: string, file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return request<MediaUploadCompleteResponse>(`/media-assets/uploads/${encodeURIComponent(uploadToken)}`, {
    method: 'PUT',
    body: formData,
  });
}

export function sortProductMedia(productId: number, payload: MediaSortPayload) {
  return jsonRequest<ProductMutationResponse>(`/products/${productId}/media-assets/sort`, 'PATCH', payload);
}

export function deleteProductMedia(productId: number, assetId: number) {
  return request<ProductMutationResponse>(`/products/${productId}/media-assets/${assetId}`, {
    method: 'DELETE',
  });
}

export function rollbackSystemConfig(configKey: string, logId: number, environment = 'prod') {
  return request<SystemConfigMutationResponse>(withQuery(`/system-configs/${encodeURIComponent(configKey)}/rollback/${logId}`, { environment }), {
    method: 'POST',
  });
}