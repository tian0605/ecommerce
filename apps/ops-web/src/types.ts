export type PaginatedResponse<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
  quick_filter_counts?: Record<string, number>;
  status_options?: string[];
  site_options?: string[];
};

export type Agent = {
  id: number;
  code: string;
  name: string;
  type: string;
  status: string;
  owner?: string | null;
  description?: string | null;
  pending_task_count?: number;
  processing_task_count?: number;
  failed_24h_count?: number;
  last_heartbeat_status?: string | null;
  updated_at?: string | null;
};

export type ComponentSummary = {
  code: string;
  name: string;
  type: string;
  status: string;
  task_count?: number;
  pending_task_count?: number;
  processing_task_count?: number;
  failed_24h_count?: number;
  last_heartbeat_status?: string | null;
  updated_at?: string | null;
};

export type Task = {
  task_name: string;
  component_code?: string | null;
  component_name?: string | null;
  display_name?: string | null;
  task_type?: string | null;
  priority?: string | null;
  status?: string | null;
  exec_state?: string | null;
  current_stage?: string | null;
  stage_status?: string | null;
  stage_result?: string | null;
  task_level?: number | null;
  parent_task_id?: string | null;
  root_task_id?: string | null;
  retry_count?: number | null;
  last_error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type TaskProgressCheckpoint = {
  current_step?: string | null;
  completed_steps?: string[];
  next_action?: string | null;
  output_data?: {
    log_tail?: string[];
    product_id?: string | null;
    url?: string | null;
    products?: string[] | null;
    product_count?: number | null;
    screenshot_path?: string | null;
    cos_url?: string | null;
  };
  url?: string | null;
  products?: string[];
  product_count?: number;
  lightweight?: boolean;
  no_publish?: boolean;
  full_workflow?: boolean;
  note?: string | null;
};

export type TaskDetailView = Task & {
  progress_checkpoint?: TaskProgressCheckpoint | null;
  notification_status?: string | null;
  feedback_doc_url?: string | null;
  feedback_markdown_file?: string | null;
};

export type WorkflowPrecheckCheck = {
  key: 'cookies' | 'ssh_tunnel' | 'local_weight' | 'postgres' | 'llm_api';
  label: string;
  status: 'passed' | 'warning' | 'failed';
  detail: string;
  hint?: string | null;
  observed_value?: string | null;
};

export type WorkflowPrecheckResponse = {
  status: 'ok' | 'warning' | 'error';
  checked_at: string;
  summary: string;
  checks: WorkflowPrecheckCheck[];
  normalized: {
    urls: string[];
    product_count: number;
    lightweight: boolean;
    publish: boolean;
  };
  can_proceed: boolean;
};

export type WorkflowLaunchPayload = {
  urls: string[];
  lightweight: boolean;
  publish: boolean;
  display_name?: string;
  expected_duration?: number;
  priority?: string;
  note?: string;
  source?: string;
};

export type WorkflowLaunchResponse = {
  status: string;
  message: string;
  task: TaskDetailView;
  launch_context: {
    urls: string[];
    product_count: number;
    lightweight: boolean;
    publish: boolean;
    expected_duration?: number | null;
  };
};

export type MarketConfigListItem = {
  id: number;
  market_code: string;
  config_name?: string | null;
  channel_code?: string | null;
  site_code?: string | null;
  default_currency?: string | null;
  source_language?: string | null;
  listing_language?: string | null;
  default_shipping_profile_code?: string | null;
  default_content_policy_code?: string | null;
  commission_free_days?: number | null;
  allow_publish?: boolean;
  allow_profit_analysis?: boolean;
  allow_listing_optimization?: boolean;
  is_active?: boolean;
  updated_at?: string | null;
};

export type MarketConfigDetail = MarketConfigListItem & {
  default_fee_profile_code?: string | null;
  default_erp_profile_code?: string | null;
  default_category_profile_code?: string | null;
  default_price_policy_code?: string | null;
  metadata?: Record<string, unknown> | null;
  effective_from?: string | null;
  effective_to?: string | null;
  created_at?: string | null;
};

export type ShippingProfileListItem = {
  id: number;
  shipping_profile_code: string;
  profile_name?: string | null;
  market_code?: string | null;
  site_code?: string | null;
  channel_name?: string | null;
  currency?: string | null;
  chargeable_weight_mode?: string | null;
  first_weight_g?: number | null;
  first_weight_fee?: number | null;
  continue_weight_g?: number | null;
  continue_weight_fee?: number | null;
  is_default?: boolean;
  is_active?: boolean;
  updated_at?: string | null;
};

export type ShippingProfileDetail = ShippingProfileListItem & {
  weight_rounding_mode?: string | null;
  weight_rounding_base_g?: number | null;
  volumetric_divisor?: number | null;
  max_weight_g?: number | null;
  shipping_subsidy_rule_type?: string | null;
  subsidy_rules_json?: Record<string, unknown> | null;
  hidden_shipping_formula?: string | null;
  hidden_shipping_continue_fee?: number | null;
  platform_shipping_fee_rate?: number | null;
  platform_shipping_fee_cap?: number | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
};

export type ContentPolicyListItem = {
  id: number;
  content_policy_code: string;
  policy_name?: string | null;
  market_code?: string | null;
  site_code?: string | null;
  prompt_profile_code?: string | null;
  source_language?: string | null;
  listing_language?: string | null;
  translation_mode?: string | null;
  title_min_length?: number | null;
  title_max_length?: number | null;
  description_min_length?: number | null;
  description_max_length?: number | null;
  is_default?: boolean;
  is_active?: boolean;
  updated_at?: string | null;
};

export type ContentPolicyDetail = ContentPolicyListItem & {
  forbidden_terms_json?: unknown[] | null;
  required_sections_json?: unknown[] | null;
  term_mapping_json?: Record<string, unknown> | null;
  validation_rule_set?: Record<string, unknown> | null;
  prompt_base_template?: string | null;
  prompt_title_variant?: string | null;
  prompt_desc_variant?: string | null;
  fallback_to_source_title?: boolean;
  fallback_to_source_description?: boolean;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
};

export type PromptProfileListItem = {
  id: number;
  prompt_profile_code: string;
  profile_name?: string | null;
  market_code?: string | null;
  site_code?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  updated_at?: string | null;
};

export type PromptProfileDetail = PromptProfileListItem & {
  title_template?: string | null;
  description_template?: string | null;
  sku_name_template?: string | null;
  template_variables_json?: Record<string, unknown> | null;
  notes?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
};

export type FeeProfileListItem = {
  id: number;
  fee_profile_code: string;
  profile_name?: string | null;
  market_code?: string | null;
  site_code?: string | null;
  currency?: string | null;
  commission_rate?: number | null;
  transaction_fee_rate?: number | null;
  pre_sale_service_rate?: number | null;
  agent_fee_cny?: number | null;
  commission_free_days?: number | null;
  is_default?: boolean;
  is_active?: boolean;
  updated_at?: string | null;
};

export type FeeProfileDetail = FeeProfileListItem & {
  tax_rate?: number | null;
  buyer_shipping_ordinary?: number | null;
  buyer_shipping_discount?: number | null;
  buyer_shipping_free?: number | null;
  hidden_price_mode?: string | null;
  hidden_price_value?: number | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
};

export type PromptPreviewResponse = {
  status: string;
  mode: string;
  prompt: string;
  preview_text?: string | null;
  preview_json?: Record<string, unknown> | null;
  prompt_source?: string | null;
  template_version?: string | null;
  rendered_variables?: Record<string, unknown> | null;
  model?: {
    name?: string | null;
    provider?: string | null;
    used_fallback?: boolean;
    success?: boolean;
  } | null;
  resolved?: {
    site_code?: string | null;
    listing_language?: string | null;
    content_policy_code?: string | null;
    prompt_profile_code?: string | null;
    product_id_new?: string | null;
  };
};

export type ProfitTrialResponse = {
  status: string;
  result?: Record<string, unknown>;
  results?: Record<string, unknown>[];
  product_summary?: Record<string, unknown> | null;
  resolved?: {
    site_code?: string | null;
    shipping_profile_code?: string | null;
    fee_profile_code?: string | null;
    product_id_new?: string | null;
  };
};

export type SiteListingListItem = {
  id: number;
  market_code?: string | null;
  site_code?: string | null;
  shop_code?: string | null;
  alibaba_product_id?: string | null;
  product_id_new?: string | null;
  listing_title?: string | null;
  content_policy_code?: string | null;
  shipping_profile_code?: string | null;
  status?: string | null;
  publish_status?: string | null;
  sync_status?: string | null;
  currency?: string | null;
  estimated_profit_local?: number | null;
  updated_at?: string | null;
};

export type SiteListingDetail = SiteListingListItem & {
  product_id?: number | null;
  sku_id?: number | null;
  shop_name?: string | null;
  platform?: string | null;
  source_language_snapshot?: string | null;
  listing_language_snapshot?: string | null;
  title_source?: string | null;
  description_source?: string | null;
  original_title_snapshot?: string | null;
  original_description_snapshot?: string | null;
  listing_description?: string | null;
  short_description?: string | null;
  fee_profile_code?: string | null;
  price_policy_code?: string | null;
  erp_profile_code?: string | null;
  category_profile_code?: string | null;
  platform_category_id?: string | null;
  platform_category_path?: unknown[] | null;
  platform_attributes_json?: Record<string, unknown> | null;
  price_amount?: number | null;
  promo_price_amount?: number | null;
  suggested_price?: number | null;
  exchange_rate_used?: number | null;
  chargeable_weight_g?: number | null;
  estimated_profit_cny?: number | null;
  profit_rate?: number | null;
  published_listing_id?: string | null;
  published_url?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  sync_error?: string | null;
  last_synced_at?: string | null;
  is_current?: boolean;
  created_at?: string | null;
  product_title?: string | null;
  product_optimized_title?: string | null;
  product_optimized_description?: string | null;
};

export type WorkflowRetryResponse = WorkflowLaunchResponse;

export type WorkflowRecentTaskItem = {
  task_name: string;
  display_name?: string | null;
  priority?: string | null;
  exec_state?: string | null;
  current_stage?: string | null;
  stage_status?: string | null;
  updated_at?: string | null;
  product_count?: number | null;
  lightweight?: boolean | null;
  publish?: boolean | null;
  current_step?: string | null;
  first_url?: string | null;
};

export type ProfitAnalysisSummary = {
  total_rows?: number;
  total_products?: number;
  total_skus?: number;
  avg_profit_rate?: number | null;
  avg_total_cost_cny?: number | null;
  avg_estimated_profit_local?: number | null;
  avg_estimated_profit_cny?: number | null;
  avg_suggested_price_local?: number | null;
  avg_suggested_price_twd?: number | null;
  currency?: string | null;
  high_profit_count?: number;
  medium_profit_count?: number;
  low_profit_count?: number;
  loss_count?: number;
  last_analysis_at?: string | null;
};

export type ProfitInitCandidateSummary = {
  total_products?: number;
  initialized_products?: number;
  missing_products?: number;
};

export type ProfitAnalysisItem = {
  id: number;
  product_id?: number | null;
  sku_id?: number | null;
  platform?: string | null;
  site?: string | null;
  site_code?: string | null;
  market_code?: string | null;
  shop_code?: string | null;
  alibaba_product_id?: string | null;
  product_id_new?: string | null;
  title?: string | null;
  sku_name?: string | null;
  purchase_price_cny?: number | null;
  suggested_price_local?: number | null;
  suggested_price_twd?: number | null;
  suggested_price_cny?: number | null;
  estimated_profit_local?: number | null;
  estimated_profit_cny?: number | null;
  shipping_cn?: number | null;
  hidden_shipping_cost_local?: number | null;
  platform_shipping_fee_local?: number | null;
  agent_fee_cny?: number | null;
  sls_fee_cny?: number | null;
  commission_local?: number | null;
  commission_cny?: number | null;
  service_fee_cny?: number | null;
  transaction_fee_cny?: number | null;
  weight_kg?: number | null;
  chargeable_weight_g?: number | null;
  package_weight?: number | null;
  package_length?: number | null;
  package_width?: number | null;
  package_height?: number | null;
  total_cost_cny?: number | null;
  profit_rate?: number | null;
  currency?: string | null;
  analysis_date?: string | null;
  remarks?: string | null;
  updated_at?: string | null;
};

export type ProfitSyncLaunchResponse = {
  status: string;
  message: string;
  task: TaskDetailView;
  launch_context: {
    alibaba_ids: string[];
    product_count: number;
    profit_rate: number;
    expected_duration?: number | null;
  };
};

export type ProfitInitLaunchResponse = {
  status: string;
  message: string;
  task: TaskDetailView;
  launch_context: {
    scope: string;
    site: string;
    candidate_count: number;
    batch_size: number;
    force_recalculate: boolean;
    profit_rate: number;
    expected_duration?: number | null;
  };
};

export type ProfitInitRetryResponse = ProfitInitLaunchResponse;

export type ProfitSyncRecentTaskItem = {
  task_name: string;
  display_name?: string | null;
  priority?: string | null;
  exec_state?: string | null;
  current_stage?: string | null;
  stage_status?: string | null;
  updated_at?: string | null;
  product_count?: number | null;
  profit_rate?: string | null;
  current_step?: string | null;
  first_id?: string | null;
};

export type ProfitInitRecentTaskItem = {
  task_name: string;
  display_name?: string | null;
  priority?: string | null;
  exec_state?: string | null;
  current_stage?: string | null;
  stage_status?: string | null;
  updated_at?: string | null;
  product_count?: number | null;
  current_step?: string | null;
  scope?: string | null;
  site?: string | null;
};

export type LogEntry = {
  log_id: number;
  component_code?: string | null;
  component_name?: string | null;
  task_name?: string | null;
  log_type?: string | null;
  log_level?: string | null;
  run_status?: string | null;
  run_message?: string | null;
  run_content?: string | null;
  duration_ms?: number | null;
  created_at?: string | null;
};

export type Heartbeat = {
  heartbeat_id: number;
  heartbeat_status?: string | null;
  summary?: string | null;
  pending_count?: number;
  processing_count?: number;
  requires_manual_count?: number;
  overtime_temp_count?: number;
  duration_ms?: number;
  report_time?: string | null;
};

export type AgentMetrics = {
  task_success_rate?: number | null;
  task_failure_count?: number;
  avg_duration_ms?: number;
  heartbeat_warning_count?: number;
  heartbeat_critical_count?: number;
  manual_queue_count?: number;
  pending_queue_count?: number;
  processing_queue_count?: number;
  fix_task_priority_distribution?: Record<string, number>;
  stage_distribution?: Record<string, number>;
  stage_status_distribution?: Record<string, number>;
  retrospective_queue_count?: number;
  blocked_stage_count?: number;
  metric_timestamp?: string | null;
  metric_window?: string;
};

export type DashboardOverview = {
  agent_count?: number;
  active_agent_count?: number;
  pending_task_count?: number;
  processing_task_count?: number;
  manual_task_count?: number;
  overtime_temp_count?: number;
  heartbeat_warning_agent_count?: number;
  heartbeat_critical_agent_count?: number;
  task_success_rate_24h?: number | null;
  stage_distribution?: Record<string, number>;
  stage_status_distribution?: Record<string, number>;
  retrospective_task_count?: number;
  blocked_stage_count?: number;
  metric_timestamp?: string | null;
};

export type ProductListItem = {
  id: number;
  alibaba_product_id?: string | null;
  product_id_new?: string | null;
  title: string;
  preview_image_url?: string | null;
  original_title?: string | null;
  status?: string | null;
  category?: string | null;
  brand?: string | null;
  sku_count?: number;
  main_image_count?: number;
  total_stock?: number;
  site_listing_count?: number;
  price_min?: number | null;
  price_max?: number | null;
  last_analysis_at?: string | null;
  published_sites?: string[];
  site_status?: Record<string, string>;
  updated_at?: string | null;
};

export type ProductSkuView = {
  id: number;
  sku_name?: string | null;
  shopee_sku_name?: string | null;
  sku_code?: string | null;
  price?: number | null;
  stock?: number | null;
  currency?: string | null;
  package_weight?: number | null;
  package_length?: number | null;
  package_width?: number | null;
  package_height?: number | null;
  image_url?: string | null;
};

export type MediaAssetView = {
  id: number;
  owner_type?: string | null;
  owner_id?: number | null;
  sku_id?: number | null;
  sku_name?: string | null;
  media_type?: string | null;
  usage_type?: string | null;
  file_name?: string | null;
  mime_type?: string | null;
  file_size_bytes?: number | null;
  status?: string | null;
  asset_url?: string | null;
  uploaded_at?: string | null;
};

export type SiteListingView = {
  id: number | string;
  site?: string | null;
  site_code?: string | null;
  shop_code?: string | null;
  optimized_title?: string | null;
  status?: string | null;
  updated_at?: string | null;
};

export type ProductDetail = {
  id: number;
  alibaba_product_id?: string | null;
  product_id_new?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  title?: string | null;
  optimized_title?: string | null;
  description?: string | null;
  optimized_description?: string | null;
  category?: string | null;
  brand?: string | null;
  origin?: string | null;
  status?: string | null;
  published_sites?: string[];
  site_status?: Record<string, string>;
  main_images?: unknown[];
  sku_images?: unknown[];
  main_media_assets?: MediaAssetView[];
  sku_media_assets?: MediaAssetView[];
  skus: ProductSkuView[];
  site_listings: SiteListingView[];
  logistics_summary?: {
    total_stock?: number;
    weight_min?: number | null;
    weight_max?: number | null;
  };
  site_summary?: {
    listing_count?: number;
    published_count?: number;
    draft_count?: number;
  };
  profit_summary?: {
    site?: string | null;
    site_code?: string | null;
    sku_count?: number;
    last_analysis_at?: string | null;
  };
};

export type ConfigChangeLogView = {
  id?: number | null;
  action_type: string;
  change_reason?: string | null;
  verify_status?: string | null;
  verify_message?: string | null;
  operator_name?: string | null;
  created_at?: string | null;
};

export type SystemConfigListItem = {
  config_key: string;
  config_name: string;
  category: string;
  environment: string;
  value_type: string;
  secret_level: string;
  value_masked?: string | null;
  is_required: boolean;
  is_active: boolean;
  last_verify_status?: string | null;
  last_verified_at?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
  expires_at?: string | null;
  source_files?: string[];
  dependent_services?: string[];
};

export type SystemConfigDetail = SystemConfigListItem & {
  description?: string | null;
  schema_json?: Record<string, unknown> | null;
  dependency_json?: Record<string, unknown> | null;
  last_verify_message?: string | null;
  file_info?: Record<string, unknown> | null;
  recent_changes: ConfigChangeLogView[];
};

export type SystemConfigSummary = {
  total_configs: number;
  failed_configs: number;
  expiring_configs: number;
  categories: Array<{
    category: string;
    total: number;
    failed: number;
    expiring: number;
    last_updated_at?: string | null;
  }>;
};

export type ProductUpdatePayload = {
  optimized_title?: string;
  optimized_description?: string;
  category?: string;
  brand?: string;
  status?: string;
};

export type ProductSkuUpdatePayload = {
  shopee_sku_name?: string;
};

export type SystemConfigUpdatePayload = {
  environment: string;
  value?: string;
  value_masked?: string;
  description?: string;
  change_reason?: string;
  verify_after_save?: boolean;
};

export type MediaUploadRequestPayload = {
  product_id: number;
  sku_id?: number;
  file_name: string;
  content_type: string;
  size_bytes: number;
  usage_type: 'main_image' | 'sku_image';
  media_type?: 'image';
};

export type SkeletonMutationResponse<TPayload> = {
  status: string;
  stage: string;
  resource: string;
  message: string;
  payload: TPayload;
};

export type ProductMutationResponse = {
  status: string;
  product: ProductDetail;
  message: string;
};

export type SystemConfigMutationResponse = {
  status: string;
  config: SystemConfigDetail;
  message: string;
};

export type OpsConfigMutationResponse<TConfig> = {
  status: string;
  config: TConfig;
  message: string;
};

export type MediaUploadTicket = {
  upload_token: string;
  expires_at: string;
  max_size_bytes: number;
};

export type MediaUploadTicketResponse = {
  status: string;
  ticket: MediaUploadTicket;
};

export type MediaUploadCompleteResponse = {
  status: string;
  asset: MediaAssetView;
  message: string;
};

export type AuthUser = {
  username: string;
  display_name: string;
  roles: string[];
};

export type AuthSessionView = {
  authenticated: boolean;
  user: AuthUser | null;
};

export type LoginPayload = {
  username: string;
  password: string;
};

export type MediaSortPayload = {
  usage_type: 'main_image' | 'sku_image';
  asset_ids: number[];
};