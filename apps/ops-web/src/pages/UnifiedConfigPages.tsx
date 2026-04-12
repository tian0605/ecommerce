import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchContentPolicies,
  fetchContentPolicy,
  fetchFeeProfile,
  fetchFeeProfiles,
  fetchMarketConfig,
  fetchMarketConfigs,
  fetchOpsSiteListing,
  fetchOpsSiteListings,
  fetchPromptProfiles,
  fetchShippingProfile,
  fetchShippingProfiles,
  fetchPromptProfile,
  generatePromptPreview,
  runProfitTrial,
  updateContentPolicy,
  updateFeeProfile,
  updateMarketConfig,
  updatePromptProfile,
  updateShippingProfile,
} from '../api';
import { useAuth } from '../auth';
import { WorkspaceSidebar } from '../components/WorkspaceSidebar';
import type {
  ContentPolicyDetail,
  ContentPolicyListItem,
  FeeProfileDetail,
  FeeProfileListItem,
  MarketConfigListItem,
  PromptPreviewResponse,
  ProfitTrialResponse,
  PromptProfileListItem,
  PromptProfileDetail,
  ShippingProfileDetail,
  ShippingProfileListItem,
} from '../types';

type BaseRecord = Record<string, unknown>;

type ContentPolicyForm = {
  policy_name: string;
  market_code: string;
  site_code: string;
  prompt_profile_code: string;
  source_language: string;
  listing_language: string;
  translation_mode: string;
  title_min_length: string;
  title_max_length: string;
  description_min_length: string;
  description_max_length: string;
  fallback_to_source_title: boolean;
  fallback_to_source_description: boolean;
  is_default: boolean;
  is_active: boolean;
  forbidden_terms_text: string;
  required_sections_text: string;
  term_mapping_text: string;
  validation_rule_set_text: string;
  metadata_text: string;
};

type PromptProfileForm = {
  profile_name: string;
  market_code: string;
  site_code: string;
  title_template: string;
  description_template: string;
  sku_name_template: string;
  notes: string;
  is_default: boolean;
  is_active: boolean;
  template_variables_text: string;
  metadata_text: string;
};

type ShippingProfileForm = {
  profile_name: string;
  market_code: string;
  site_code: string;
  channel_name: string;
  currency: string;
  chargeable_weight_mode: string;
  weight_rounding_mode: string;
  weight_rounding_base_g: string;
  volumetric_divisor: string;
  first_weight_g: string;
  first_weight_fee: string;
  continue_weight_g: string;
  continue_weight_fee: string;
  max_weight_g: string;
  shipping_subsidy_rule_type: string;
  hidden_shipping_formula: string;
  hidden_shipping_continue_fee: string;
  platform_shipping_fee_rate: string;
  platform_shipping_fee_cap: string;
  is_default: boolean;
  is_active: boolean;
  subsidy_rules_text: string;
  metadata_text: string;
};

type FeeProfileForm = {
  profile_name: string;
  market_code: string;
  site_code: string;
  currency: string;
  commission_rate: string;
  transaction_fee_rate: string;
  pre_sale_service_rate: string;
  tax_rate: string;
  agent_fee_cny: string;
  commission_free_days: string;
  buyer_shipping_ordinary: string;
  buyer_shipping_discount: string;
  buyer_shipping_free: string;
  hidden_price_mode: string;
  hidden_price_value: string;
  is_default: boolean;
  is_active: boolean;
  metadata_text: string;
};

type MarketConfigForm = {
  config_name: string;
  channel_code: string;
  site_code: string;
  default_currency: string;
  source_language: string;
  listing_language: string;
  default_shipping_profile_code: string;
  default_content_policy_code: string;
  default_fee_profile_code: string;
  commission_free_days: string;
  default_erp_profile_code: string;
  default_category_profile_code: string;
  default_price_policy_code: string;
  allow_publish: boolean;
  allow_profit_analysis: boolean;
  allow_listing_optimization: boolean;
  is_active: boolean;
  effective_from: string;
  effective_to: string;
  metadata_text: string;
};

type ProductDebugForm = {
  product_id_new: string;
  market_code: string;
  site_code: string;
  content_policy_code: string;
  prompt_profile_code: string;
  shipping_profile_code: string;
  fee_profile_code: string;
  mode: 'title' | 'description' | 'sku';
  target_profit_rate: string;
};

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

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function toJsonText(value: unknown) {
  if (value == null) {
    return '{}';
  }
  return formatJson(value);
}

function toArrayText(value: unknown) {
  if (!Array.isArray(value)) {
    return '';
  }
  return value.map((item) => String(item ?? '')).join('\n');
}

function parseNullableNumber(value: string, label: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${label} 必须是数字`);
  }
  return parsed;
}

function parseJsonObject(text: string, label: string) {
  const trimmed = text.trim();
  if (!trimmed) {
    return {};
  }
  const parsed = JSON.parse(trimmed) as unknown;
  if (parsed == null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return parsed as Record<string, unknown>;
}

function parseJsonValue(text: string, label: string) {
  const trimmed = text.trim();
  if (!trimmed) {
    return {};
  }
  try {
    return JSON.parse(trimmed) as unknown;
  } catch {
    throw new Error(`${label} 不是合法 JSON`);
  }
}

function parseStringLines(text: string) {
  return text
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function toDatetimeLocalValue(value?: string | null) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function fromDatetimeLocalValue(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  return new Date(trimmed).toISOString();
}

function ConfigListPanel<T extends BaseRecord>(props: {
  title: string;
  total: number;
  primaryField: keyof T & string;
  secondaryField?: keyof T & string;
  items: T[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
  emptyLabelField?: keyof T & string;
}) {
  return (
    <div className="table-card list-surface">
      <div className="section-head">
        <h3>{props.title}</h3>
        <span>{props.total}</span>
      </div>
      <div className="record-list">
        {props.items.map((item) => {
          const keyValue = item[props.primaryField];
          const keyText = typeof keyValue === 'string' ? keyValue : String(keyValue ?? '');
          const secondaryRaw = props.secondaryField ? item[props.secondaryField] : null;
          const secondaryText = secondaryRaw == null ? '' : String(secondaryRaw);
          const labelField = props.emptyLabelField ? item[props.emptyLabelField] : null;
          const labelText = String(labelField ?? item.site_code ?? '');
          return (
            <button key={keyText} className={`record-item ${props.selectedKey === keyText ? 'active' : ''}`} onClick={() => props.onSelect(keyText)}>
              <div className="record-item-head">
                <strong>{keyText}</strong>
                <span className={`status-pill ${item.is_active === false ? 'danger' : 'success'}`}>
                  {item.is_active === false ? 'inactive' : 'active'}
                </span>
              </div>
              <p>{labelText}</p>
              {secondaryText ? <div className="inline-meta">{secondaryText}</div> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}



function ReadonlySummary(props: { title: string; data: BaseRecord }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="record-item static">
      <strong style={{ cursor: 'pointer' }} onClick={() => setOpen((v) => !v)}>
        {props.title}
        <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>{open ? '（点击收起）' : '（点击展开）'}</span>
      </strong>
      {open && <pre className="config-json-preview">{formatJson(props.data)}</pre>}
    </div>
  );
}

function ContentPromptPanel(props: {
  promptProfileCode: string | null;
  promptDetail: PromptProfileDetail | undefined;
  promptForm: PromptProfileForm | null;
  setPromptForm: Dispatch<SetStateAction<PromptProfileForm | null>>;
  promptPending: boolean;
  promptMessage: string;
  onSave: () => void;
}) {
  if (!props.promptProfileCode) {
    return <PageState title="未选择提示词模板" detail="先从左侧选择内容策略或提示词模板。" />;
  }

  if (!props.promptDetail || !props.promptForm) {
    return <PageState title="提示词模板加载中" detail="正在读取关联模板内容。" />;
  }

  return (
    <div className="record-item static">
      <div className="section-head compact">
        <h3>提示词模板</h3>
        <span>{props.promptProfileCode}</span>
      </div>
      <ReadonlySummary title="提示词模板摘要" data={props.promptDetail as BaseRecord} />
      <div className="config-form-grid">
        <label className="form-field"><span>模板名称</span><input className="filter-input" value={props.promptForm.profile_name} onChange={(event) => props.setPromptForm((current) => current ? { ...current, profile_name: event.target.value } : current)} /></label>
        <label className="form-field"><span>市场编码</span><input className="filter-input" value={props.promptForm.market_code} onChange={(event) => props.setPromptForm((current) => current ? { ...current, market_code: event.target.value } : current)} /></label>
        <label className="form-field"><span>站点编码</span><input className="filter-input" value={props.promptForm.site_code} onChange={(event) => props.setPromptForm((current) => current ? { ...current, site_code: event.target.value } : current)} /></label>
      </div>
      <div className="config-toggle-grid">
        <label className="inline-checkbox"><input type="checkbox" checked={props.promptForm.is_default} onChange={(event) => props.setPromptForm((current) => current ? { ...current, is_default: event.target.checked } : current)} />默认模板</label>
        <label className="inline-checkbox"><input type="checkbox" checked={props.promptForm.is_active} onChange={(event) => props.setPromptForm((current) => current ? { ...current, is_active: event.target.checked } : current)} />启用模板</label>
      </div>
      <label className="form-field form-field-full config-section"><span>标题模板</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={props.promptForm.title_template} onChange={(event) => props.setPromptForm((current) => current ? { ...current, title_template: event.target.value } : current)} /></label>
      <label className="form-field form-field-full config-section"><span>描述模板</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={props.promptForm.description_template} onChange={(event) => props.setPromptForm((current) => current ? { ...current, description_template: event.target.value } : current)} /></label>
      <label className="form-field form-field-full config-section"><span>SKU 名称模板</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={props.promptForm.sku_name_template} onChange={(event) => props.setPromptForm((current) => current ? { ...current, sku_name_template: event.target.value } : current)} /></label>
      <label className="form-field form-field-full config-section"><span>模板变量 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={props.promptForm.template_variables_text} onChange={(event) => props.setPromptForm((current) => current ? { ...current, template_variables_text: event.target.value } : current)} /></label>
      <label className="form-field form-field-full config-section"><span>备注</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={props.promptForm.notes} onChange={(event) => props.setPromptForm((current) => current ? { ...current, notes: event.target.value } : current)} /></label>
      <label className="form-field form-field-full config-section"><span>元数据 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={props.promptForm.metadata_text} onChange={(event) => props.setPromptForm((current) => current ? { ...current, metadata_text: event.target.value } : current)} /></label>
      <div className="form-actions">
        <button className="ghost-button" onClick={props.onSave} disabled={props.promptPending}>{props.promptPending ? '保存中...' : '保存提示词模板'}</button>
      </div>
      {props.promptMessage ? <div className="inline-meta config-save-message">{props.promptMessage}</div> : null}
    </div>
  );
}

function FeeRulePanel(props: {
  feeProfileCode: string | null;
  feeDetail: FeeProfileDetail | undefined;
  feeForm: FeeProfileForm | null;
  setFeeForm: Dispatch<SetStateAction<FeeProfileForm | null>>;
  feePending: boolean;
  feeMessage: string;
  onSave: () => void;
}) {
  if (!props.feeProfileCode) {
    return <PageState title="未匹配利润规则" detail="当前物流模板没有找到同站点的利润规则。" />;
  }

  if (!props.feeDetail || !props.feeForm) {
    return <PageState title="利润规则加载中" detail="正在读取关联利润规则。" />;
  }

  return (
    <div className="record-item static">
      <div className="section-head compact">
        <h3>利润规则</h3>
        <span>{props.feeProfileCode}</span>
      </div>
      <ReadonlySummary title="利润规则摘要" data={props.feeDetail as BaseRecord} />
      <div className="config-form-grid">
        <label className="form-field"><span>规则名称</span><input className="filter-input" value={props.feeForm.profile_name} onChange={(event) => props.setFeeForm((current) => current ? { ...current, profile_name: event.target.value } : current)} /></label>
        <label className="form-field"><span>市场编码</span><input className="filter-input" value={props.feeForm.market_code} onChange={(event) => props.setFeeForm((current) => current ? { ...current, market_code: event.target.value } : current)} /></label>
        <label className="form-field"><span>站点编码</span><input className="filter-input" value={props.feeForm.site_code} onChange={(event) => props.setFeeForm((current) => current ? { ...current, site_code: event.target.value } : current)} /></label>
        <label className="form-field"><span>币种</span><input className="filter-input" value={props.feeForm.currency} onChange={(event) => props.setFeeForm((current) => current ? { ...current, currency: event.target.value } : current)} /></label>
        <label className="form-field"><span>佣金率</span><input className="filter-input" value={props.feeForm.commission_rate} onChange={(event) => props.setFeeForm((current) => current ? { ...current, commission_rate: event.target.value } : current)} /></label>
        <label className="form-field"><span>交易手续费率</span><input className="filter-input" value={props.feeForm.transaction_fee_rate} onChange={(event) => props.setFeeForm((current) => current ? { ...current, transaction_fee_rate: event.target.value } : current)} /></label>
        <label className="form-field"><span>预售服务费率</span><input className="filter-input" value={props.feeForm.pre_sale_service_rate} onChange={(event) => props.setFeeForm((current) => current ? { ...current, pre_sale_service_rate: event.target.value } : current)} /></label>
        <label className="form-field"><span>税费率</span><input className="filter-input" value={props.feeForm.tax_rate} onChange={(event) => props.setFeeForm((current) => current ? { ...current, tax_rate: event.target.value } : current)} /></label>
        <label className="form-field"><span>货代费(CNY)</span><input className="filter-input" value={props.feeForm.agent_fee_cny} onChange={(event) => props.setFeeForm((current) => current ? { ...current, agent_fee_cny: event.target.value } : current)} /></label>
        <label className="form-field"><span>免佣天数</span><input className="filter-input" value={props.feeForm.commission_free_days} onChange={(event) => props.setFeeForm((current) => current ? { ...current, commission_free_days: event.target.value } : current)} /></label>
        <label className="form-field"><span>普通买家运费</span><input className="filter-input" value={props.feeForm.buyer_shipping_ordinary} onChange={(event) => props.setFeeForm((current) => current ? { ...current, buyer_shipping_ordinary: event.target.value } : current)} /></label>
        <label className="form-field"><span>折扣买家运费</span><input className="filter-input" value={props.feeForm.buyer_shipping_discount} onChange={(event) => props.setFeeForm((current) => current ? { ...current, buyer_shipping_discount: event.target.value } : current)} /></label>
        <label className="form-field"><span>免运买家运费</span><input className="filter-input" value={props.feeForm.buyer_shipping_free} onChange={(event) => props.setFeeForm((current) => current ? { ...current, buyer_shipping_free: event.target.value } : current)} /></label>
        <label className="form-field"><span>藏价模式</span><input className="filter-input" value={props.feeForm.hidden_price_mode} onChange={(event) => props.setFeeForm((current) => current ? { ...current, hidden_price_mode: event.target.value } : current)} /></label>
        <label className="form-field"><span>藏价值</span><input className="filter-input" value={props.feeForm.hidden_price_value} onChange={(event) => props.setFeeForm((current) => current ? { ...current, hidden_price_value: event.target.value } : current)} /></label>
      </div>
      <div className="config-toggle-grid">
        <label className="inline-checkbox"><input type="checkbox" checked={props.feeForm.is_default} onChange={(event) => props.setFeeForm((current) => current ? { ...current, is_default: event.target.checked } : current)} />默认规则</label>
        <label className="inline-checkbox"><input type="checkbox" checked={props.feeForm.is_active} onChange={(event) => props.setFeeForm((current) => current ? { ...current, is_active: event.target.checked } : current)} />启用规则</label>
      </div>
      <label className="form-field form-field-full config-section"><span>元数据 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={props.feeForm.metadata_text} onChange={(event) => props.setFeeForm((current) => current ? { ...current, metadata_text: event.target.value } : current)} /></label>
      <div className="form-actions">
        <button className="ghost-button" onClick={props.onSave} disabled={props.feePending}>{props.feePending ? '保存中...' : '保存利润规则'}</button>
      </div>
      {props.feeMessage ? <div className="inline-meta config-save-message">{props.feeMessage}</div> : null}
    </div>
  );
}

export function ContentPromptConfigPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState('');
  const [siteCode, setSiteCode] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedPromptKey, setSelectedPromptKey] = useState<string | null>(null);
  const [contentForm, setContentForm] = useState<ContentPolicyForm | null>(null);
  const [promptForm, setPromptForm] = useState<PromptProfileForm | null>(null);
  const [contentMessage, setContentMessage] = useState('');
  const [promptMessage, setPromptMessage] = useState('');

  const listQuery = useQuery({
    queryKey: ['content-policies', 'merged-list', keyword, siteCode, showInactive],
    queryFn: () => fetchContentPolicies({ page: 1, pageSize: 100, keyword, siteCode, isActive: showInactive ? undefined : true }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!selectedKey && listQuery.data?.items?.length) {
      setSelectedKey(listQuery.data.items[0]?.content_policy_code ?? null);
    }
  }, [listQuery.data, selectedKey]);

  const detailQuery = useQuery({
    queryKey: ['content-policies', 'merged-detail', selectedKey],
    queryFn: () => fetchContentPolicy(selectedKey as string),
    enabled: selectedKey != null,
  });

  const promptListQuery = useQuery({
    queryKey: ['prompt-profiles', 'merged-list', keyword, siteCode, showInactive],
    queryFn: () => fetchPromptProfiles({ page: 1, pageSize: 100, keyword, siteCode, isActive: showInactive ? undefined : true }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!detailQuery.data) {
      return;
    }
    setContentForm({
      policy_name: detailQuery.data.policy_name ?? '',
      market_code: detailQuery.data.market_code ?? '',
      site_code: detailQuery.data.site_code ?? '',
      prompt_profile_code: detailQuery.data.prompt_profile_code ?? '',
      source_language: detailQuery.data.source_language ?? '',
      listing_language: detailQuery.data.listing_language ?? '',
      translation_mode: detailQuery.data.translation_mode ?? '',
      title_min_length: detailQuery.data.title_min_length == null ? '' : String(detailQuery.data.title_min_length),
      title_max_length: detailQuery.data.title_max_length == null ? '' : String(detailQuery.data.title_max_length),
      description_min_length: detailQuery.data.description_min_length == null ? '' : String(detailQuery.data.description_min_length),
      description_max_length: detailQuery.data.description_max_length == null ? '' : String(detailQuery.data.description_max_length),
      fallback_to_source_title: detailQuery.data.fallback_to_source_title === true,
      fallback_to_source_description: detailQuery.data.fallback_to_source_description === true,
      is_default: detailQuery.data.is_default === true,
      is_active: detailQuery.data.is_active !== false,
      forbidden_terms_text: toArrayText(detailQuery.data.forbidden_terms_json),
      required_sections_text: toArrayText(detailQuery.data.required_sections_json),
      term_mapping_text: toJsonText(detailQuery.data.term_mapping_json),
      validation_rule_set_text: toJsonText(detailQuery.data.validation_rule_set),
      metadata_text: toJsonText(detailQuery.data.metadata),
    });
    setContentMessage('');
  }, [detailQuery.data]);

  const linkedPromptProfileCode = useMemo(() => {
    const explicitCode = contentForm?.prompt_profile_code.trim();
    if (explicitCode) {
      return explicitCode;
    }
    if (detailQuery.data?.prompt_profile_code) {
      return detailQuery.data.prompt_profile_code;
    }
    return selectedKey ? `prompt_${selectedKey}` : null;
  }, [contentForm?.prompt_profile_code, detailQuery.data?.prompt_profile_code, selectedKey]);

  useEffect(() => {
    if (linkedPromptProfileCode) {
      setSelectedPromptKey(linkedPromptProfileCode);
    }
  }, [selectedKey, linkedPromptProfileCode]);

  useEffect(() => {
    if (!selectedPromptKey && promptListQuery.data?.items?.length) {
      setSelectedPromptKey(promptListQuery.data.items[0]?.prompt_profile_code ?? null);
    }
  }, [promptListQuery.data, selectedPromptKey]);

  const promptProfileCode = selectedPromptKey ?? linkedPromptProfileCode;

  const promptDetailQuery = useQuery({
    queryKey: ['prompt-profiles', 'linked-detail', promptProfileCode],
    queryFn: () => fetchPromptProfile(promptProfileCode as string),
    enabled: promptProfileCode != null,
  });

  useEffect(() => {
    if (!promptDetailQuery.data) {
      return;
    }
    setPromptForm({
      profile_name: promptDetailQuery.data.profile_name ?? '',
      market_code: promptDetailQuery.data.market_code ?? '',
      site_code: promptDetailQuery.data.site_code ?? '',
      title_template: promptDetailQuery.data.title_template ?? '',
      description_template: promptDetailQuery.data.description_template ?? '',
      sku_name_template: promptDetailQuery.data.sku_name_template ?? '',
      notes: promptDetailQuery.data.notes ?? '',
      is_default: promptDetailQuery.data.is_default === true,
      is_active: promptDetailQuery.data.is_active !== false,
      template_variables_text: toJsonText(promptDetailQuery.data.template_variables_json),
      metadata_text: toJsonText(promptDetailQuery.data.metadata),
    });
    setPromptMessage('');
  }, [promptDetailQuery.data]);

  const contentMutation = useMutation({
    mutationFn: () => {
      if (!selectedKey || !contentForm) {
        throw new Error('请先选择一条内容策略');
      }
      return updateContentPolicy(selectedKey, {
        policy_name: contentForm.policy_name.trim(),
        market_code: contentForm.market_code.trim(),
        site_code: contentForm.site_code.trim(),
        prompt_profile_code: contentForm.prompt_profile_code.trim() || null,
        source_language: contentForm.source_language.trim(),
        listing_language: contentForm.listing_language.trim(),
        translation_mode: contentForm.translation_mode.trim(),
        title_min_length: parseNullableNumber(contentForm.title_min_length, '标题最短长度'),
        title_max_length: parseNullableNumber(contentForm.title_max_length, '标题最长长度'),
        description_min_length: parseNullableNumber(contentForm.description_min_length, '描述最短长度'),
        description_max_length: parseNullableNumber(contentForm.description_max_length, '描述最长长度'),
        forbidden_terms_json: parseStringLines(contentForm.forbidden_terms_text),
        required_sections_json: parseStringLines(contentForm.required_sections_text),
        term_mapping_json: parseJsonObject(contentForm.term_mapping_text, '术语映射'),
        validation_rule_set: parseJsonObject(contentForm.validation_rule_set_text, '校验规则'),
        fallback_to_source_title: contentForm.fallback_to_source_title,
        fallback_to_source_description: contentForm.fallback_to_source_description,
        is_default: contentForm.is_default,
        is_active: contentForm.is_active,
        metadata: parseJsonObject(contentForm.metadata_text, '内容策略元数据'),
      });
    },
    onSuccess: async (response) => {
      setContentMessage(response.message);
      await queryClient.invalidateQueries({ queryKey: ['content-policies'] });
    },
    onError: (error) => {
      setContentMessage(error instanceof Error ? error.message : '保存失败');
    },
  });

  const promptMutation = useMutation({
    mutationFn: () => {
      if (!promptProfileCode || !promptForm) {
        throw new Error('请先绑定提示词模板');
      }
      return updatePromptProfile(promptProfileCode, {
        profile_name: promptForm.profile_name.trim(),
        market_code: promptForm.market_code.trim() || null,
        site_code: promptForm.site_code.trim(),
        title_template: promptForm.title_template.trim() || null,
        description_template: promptForm.description_template.trim() || null,
        sku_name_template: promptForm.sku_name_template.trim() || null,
        notes: promptForm.notes.trim() || null,
        is_default: promptForm.is_default,
        is_active: promptForm.is_active,
        template_variables_json: parseJsonObject(promptForm.template_variables_text, '模板变量'),
        metadata: parseJsonObject(promptForm.metadata_text, '提示词元数据'),
      });
    },
    onSuccess: async (response) => {
      setPromptMessage(response.message);
      await queryClient.invalidateQueries({ queryKey: ['prompt-profiles'] });
    },
    onError: (error) => {
      setPromptMessage(error instanceof Error ? error.message : '保存失败');
    },
  });

  const activeCount = useMemo(() => (listQuery.data?.items ?? []).filter((item) => item.is_active !== false).length, [listQuery.data]);

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Content + Prompt</span>
          <h1>内容与提示词</h1>
          <p>内容规则和提示词模板统一维护。模板默认值已按现有 prompt 文件完成初始化。</p>
        </div>
        <div className="agent-list-card">
          <div className="section-head compact"><h2>筛选</h2><span>{listQuery.data?.total ?? 0}</span></div>
          <div className="filter-stack">
            <input className="filter-input" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索编码 / 名称 / 站点" />
            <input className="filter-input" value={siteCode} onChange={(event) => setSiteCode(event.target.value)} placeholder="site_code，例如 shopee_tw" />
            <label className="inline-checkbox"><input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} />显示停用配置</label>
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Config Center</span>
            <h2>内容规则 + Prompt 资产</h2>
            <p>左边同时查看内容策略和全站点提示词模板，右边统一编辑当前规则层与模板层。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">rules</span>
            <span className="status-pill success">prompt-assets</span>
          </div>
        </section>

        <section className="metrics-grid page-metrics-grid">
          <div className="metric-card"><span className="metric-label">记录总数</span><strong className="metric-value" data-accent="blue">{listQuery.data?.total ?? 0}</strong></div>
          <div className="metric-card"><span className="metric-label">启用中</span><strong className="metric-value" data-accent="green">{activeCount}</strong></div>
          <div className="metric-card"><span className="metric-label">当前会话</span><strong className="metric-value" data-accent="amber">{session.user?.display_name ?? '未登录'}</strong></div>
        </section>

        <section className="detail-layout">
          <div className="panel-column">
            <ConfigListPanel<PromptProfileListItem>
              title="提示词模板"
              total={promptListQuery.data?.total ?? 0}
              primaryField="prompt_profile_code"
              secondaryField="site_code"
              emptyLabelField="profile_name"
              items={promptListQuery.data?.items ?? []}
              selectedKey={selectedPromptKey}
              onSelect={setSelectedPromptKey}
            />
            <ConfigListPanel<ContentPolicyListItem>
              title="内容策略"
              total={listQuery.data?.total ?? 0}
              primaryField="content_policy_code"
              secondaryField="site_code"
              emptyLabelField="policy_name"
              items={listQuery.data?.items ?? []}
              selectedKey={selectedKey}
              onSelect={setSelectedKey}
            />
          </div>

          <div className="table-card list-surface">
            <div className="section-head"><h3>整合编辑</h3><span>{selectedPromptKey ?? '未选择'}</span></div>
            {promptDetailQuery.isLoading ? <PageState title="正在加载提示词模板" detail="读取标题、描述和 SKU 模板。" /> : promptDetailQuery.isError ? <PageState title="提示词模板加载失败" detail={promptDetailQuery.error instanceof Error ? promptDetailQuery.error.message : 'unknown error'} /> : !promptDetailQuery.data || !promptForm ? <PageState title="暂无模板详情" detail="先从左侧选择一个提示词模板。" /> : (
              <ContentPromptPanel promptProfileCode={promptProfileCode} promptDetail={promptDetailQuery.data} promptForm={promptForm} setPromptForm={setPromptForm} promptPending={promptMutation.isPending} promptMessage={promptMessage} onSave={() => promptMutation.mutate()} />
            )}
            <div style={{ marginTop: 32 }} />
            <div className="section-head"><h3>内容策略编辑</h3><span>{selectedKey ?? '未选择'}</span></div>
            {detailQuery.isLoading ? <PageState title="正在加载内容策略" detail="读取规则和关联模板。" /> : detailQuery.isError ? <PageState title="内容策略加载失败" detail={detailQuery.error instanceof Error ? detailQuery.error.message : 'unknown error'} /> : !detailQuery.data || !contentForm ? <PageState title="暂无配置详情" detail="先从左侧选择一条内容策略。" /> : (
              <div className="panel-column">
                <ReadonlySummary title="内容策略摘要" data={detailQuery.data as BaseRecord} />
                <div className="record-item static">
                  <div className="section-head compact"><h3>内容规则</h3><span>{contentMutation.isPending ? 'saving' : 'ready'}</span></div>
                  <div className="config-form-grid">
                    <label className="form-field"><span>策略名称</span><input className="filter-input" value={contentForm.policy_name} onChange={(event) => setContentForm((current) => current ? { ...current, policy_name: event.target.value } : current)} /></label>
                    <label className="form-field"><span>市场编码</span><input className="filter-input" value={contentForm.market_code} onChange={(event) => setContentForm((current) => current ? { ...current, market_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>站点编码</span><input className="filter-input" value={contentForm.site_code} onChange={(event) => setContentForm((current) => current ? { ...current, site_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>提示词模板编码</span><input className="filter-input" value={contentForm.prompt_profile_code} onChange={(event) => setContentForm((current) => current ? { ...current, prompt_profile_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>源语言</span><input className="filter-input" value={contentForm.source_language} onChange={(event) => setContentForm((current) => current ? { ...current, source_language: event.target.value } : current)} /></label>
                    <label className="form-field"><span>上架语言</span><input className="filter-input" value={contentForm.listing_language} onChange={(event) => setContentForm((current) => current ? { ...current, listing_language: event.target.value } : current)} /></label>
                    <label className="form-field"><span>翻译模式</span><input className="filter-input" value={contentForm.translation_mode} onChange={(event) => setContentForm((current) => current ? { ...current, translation_mode: event.target.value } : current)} /></label>
                    <label className="form-field"><span>标题最短长度</span><input className="filter-input" value={contentForm.title_min_length} onChange={(event) => setContentForm((current) => current ? { ...current, title_min_length: event.target.value } : current)} /></label>
                    <label className="form-field"><span>标题最长长度</span><input className="filter-input" value={contentForm.title_max_length} onChange={(event) => setContentForm((current) => current ? { ...current, title_max_length: event.target.value } : current)} /></label>
                    <label className="form-field"><span>描述最短长度</span><input className="filter-input" value={contentForm.description_min_length} onChange={(event) => setContentForm((current) => current ? { ...current, description_min_length: event.target.value } : current)} /></label>
                    <label className="form-field"><span>描述最长长度</span><input className="filter-input" value={contentForm.description_max_length} onChange={(event) => setContentForm((current) => current ? { ...current, description_max_length: event.target.value } : current)} /></label>
                  </div>
                  <div className="config-toggle-grid">
                    <label className="inline-checkbox"><input type="checkbox" checked={contentForm.fallback_to_source_title} onChange={(event) => setContentForm((current) => current ? { ...current, fallback_to_source_title: event.target.checked } : current)} />标题允许回退</label>
                    <label className="inline-checkbox"><input type="checkbox" checked={contentForm.fallback_to_source_description} onChange={(event) => setContentForm((current) => current ? { ...current, fallback_to_source_description: event.target.checked } : current)} />描述允许回退</label>
                    <label className="inline-checkbox"><input type="checkbox" checked={contentForm.is_default} onChange={(event) => setContentForm((current) => current ? { ...current, is_default: event.target.checked } : current)} />默认策略</label>
                    <label className="inline-checkbox"><input type="checkbox" checked={contentForm.is_active} onChange={(event) => setContentForm((current) => current ? { ...current, is_active: event.target.checked } : current)} />启用策略</label>
                  </div>
                  <div className="config-form-grid">
                    <label className="form-field config-section"><span>禁词列表</span><textarea className="form-textarea config-textarea-medium" value={contentForm.forbidden_terms_text} onChange={(event) => setContentForm((current) => current ? { ...current, forbidden_terms_text: event.target.value } : current)} /></label>
                    <label className="form-field config-section"><span>必含章节</span><textarea className="form-textarea config-textarea-medium" value={contentForm.required_sections_text} onChange={(event) => setContentForm((current) => current ? { ...current, required_sections_text: event.target.value } : current)} /></label>
                    <label className="form-field config-section"><span>术语映射 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={contentForm.term_mapping_text} onChange={(event) => setContentForm((current) => current ? { ...current, term_mapping_text: event.target.value } : current)} /></label>
                    <label className="form-field config-section"><span>校验规则 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={contentForm.validation_rule_set_text} onChange={(event) => setContentForm((current) => current ? { ...current, validation_rule_set_text: event.target.value } : current)} /></label>
                    <label className="form-field config-section"><span>元数据 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={contentForm.metadata_text} onChange={(event) => setContentForm((current) => current ? { ...current, metadata_text: event.target.value } : current)} /></label>
                  </div>
                  <div className="form-actions">
                    <button className="ghost-button" onClick={() => contentMutation.mutate()} disabled={contentMutation.isPending}>{contentMutation.isPending ? '保存中...' : '保存内容规则'}</button>
                  </div>
                  {contentMessage ? <div className="inline-meta config-save-message">{contentMessage}</div> : null}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export function LogisticsProfitConfigPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState('');
  const [siteCode, setSiteCode] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [shippingForm, setShippingForm] = useState<ShippingProfileForm | null>(null);
  const [feeForm, setFeeForm] = useState<FeeProfileForm | null>(null);
  const [shippingMessage, setShippingMessage] = useState('');
  const [feeMessage, setFeeMessage] = useState('');

  const listQuery = useQuery({
    queryKey: ['shipping-profiles', 'merged-list', keyword, siteCode, showInactive],
    queryFn: () => fetchShippingProfiles({ page: 1, pageSize: 100, keyword, siteCode, isActive: showInactive ? undefined : true }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!selectedKey && listQuery.data?.items?.length) {
      setSelectedKey(listQuery.data.items[0]?.shipping_profile_code ?? null);
    }
  }, [listQuery.data, selectedKey]);

  const detailQuery = useQuery({
    queryKey: ['shipping-profiles', 'merged-detail', selectedKey],
    queryFn: () => fetchShippingProfile(selectedKey as string),
    enabled: selectedKey != null,
  });

  useEffect(() => {
    if (!detailQuery.data) {
      return;
    }
    setShippingForm({
      profile_name: detailQuery.data.profile_name ?? '',
      market_code: detailQuery.data.market_code ?? '',
      site_code: detailQuery.data.site_code ?? '',
      channel_name: detailQuery.data.channel_name ?? '',
      currency: detailQuery.data.currency ?? '',
      chargeable_weight_mode: detailQuery.data.chargeable_weight_mode ?? '',
      weight_rounding_mode: detailQuery.data.weight_rounding_mode ?? '',
      weight_rounding_base_g: detailQuery.data.weight_rounding_base_g == null ? '' : String(detailQuery.data.weight_rounding_base_g),
      volumetric_divisor: detailQuery.data.volumetric_divisor == null ? '' : String(detailQuery.data.volumetric_divisor),
      first_weight_g: detailQuery.data.first_weight_g == null ? '' : String(detailQuery.data.first_weight_g),
      first_weight_fee: detailQuery.data.first_weight_fee == null ? '' : String(detailQuery.data.first_weight_fee),
      continue_weight_g: detailQuery.data.continue_weight_g == null ? '' : String(detailQuery.data.continue_weight_g),
      continue_weight_fee: detailQuery.data.continue_weight_fee == null ? '' : String(detailQuery.data.continue_weight_fee),
      max_weight_g: detailQuery.data.max_weight_g == null ? '' : String(detailQuery.data.max_weight_g),
      shipping_subsidy_rule_type: detailQuery.data.shipping_subsidy_rule_type ?? '',
      hidden_shipping_formula: detailQuery.data.hidden_shipping_formula ?? '',
      hidden_shipping_continue_fee: detailQuery.data.hidden_shipping_continue_fee == null ? '' : String(detailQuery.data.hidden_shipping_continue_fee),
      platform_shipping_fee_rate: detailQuery.data.platform_shipping_fee_rate == null ? '' : String(detailQuery.data.platform_shipping_fee_rate),
      platform_shipping_fee_cap: detailQuery.data.platform_shipping_fee_cap == null ? '' : String(detailQuery.data.platform_shipping_fee_cap),
      is_default: detailQuery.data.is_default === true,
      is_active: detailQuery.data.is_active !== false,
      subsidy_rules_text: toJsonText(detailQuery.data.subsidy_rules_json),
      metadata_text: toJsonText(detailQuery.data.metadata),
    });
    setShippingMessage('');
  }, [detailQuery.data]);

  const feeListQuery = useQuery({
    queryKey: ['fee-profiles', 'linked-list', detailQuery.data?.site_code, detailQuery.data?.market_code],
    queryFn: () => fetchFeeProfiles({ page: 1, pageSize: 20, siteCode: detailQuery.data?.site_code ?? undefined }),
    enabled: Boolean(detailQuery.data?.site_code),
  });

  const feeProfileCode = useMemo(() => {
    const exactMatch = (feeListQuery.data?.items ?? []).find((item) => item.market_code === detailQuery.data?.market_code)?.fee_profile_code;
    if (exactMatch) {
      return exactMatch;
    }
    const firstMatch = feeListQuery.data?.items?.[0]?.fee_profile_code;
    if (firstMatch) {
      return firstMatch;
    }
    return detailQuery.data?.market_code ? `fee_${detailQuery.data.market_code}` : null;
  }, [detailQuery.data?.market_code, feeListQuery.data?.items]);

  const feeDetailQuery = useQuery({
    queryKey: ['fee-profiles', 'linked-detail', feeProfileCode],
    queryFn: () => fetchFeeProfile(feeProfileCode as string),
    enabled: feeProfileCode != null,
  });

  useEffect(() => {
    if (!feeDetailQuery.data) {
      return;
    }
    setFeeForm({
      profile_name: feeDetailQuery.data.profile_name ?? '',
      market_code: feeDetailQuery.data.market_code ?? '',
      site_code: feeDetailQuery.data.site_code ?? '',
      currency: feeDetailQuery.data.currency ?? '',
      commission_rate: feeDetailQuery.data.commission_rate == null ? '' : String(feeDetailQuery.data.commission_rate),
      transaction_fee_rate: feeDetailQuery.data.transaction_fee_rate == null ? '' : String(feeDetailQuery.data.transaction_fee_rate),
      pre_sale_service_rate: feeDetailQuery.data.pre_sale_service_rate == null ? '' : String(feeDetailQuery.data.pre_sale_service_rate),
      tax_rate: feeDetailQuery.data.tax_rate == null ? '' : String(feeDetailQuery.data.tax_rate),
      agent_fee_cny: feeDetailQuery.data.agent_fee_cny == null ? '' : String(feeDetailQuery.data.agent_fee_cny),
      commission_free_days: feeDetailQuery.data.commission_free_days == null ? '' : String(feeDetailQuery.data.commission_free_days),
      buyer_shipping_ordinary: feeDetailQuery.data.buyer_shipping_ordinary == null ? '' : String(feeDetailQuery.data.buyer_shipping_ordinary),
      buyer_shipping_discount: feeDetailQuery.data.buyer_shipping_discount == null ? '' : String(feeDetailQuery.data.buyer_shipping_discount),
      buyer_shipping_free: feeDetailQuery.data.buyer_shipping_free == null ? '' : String(feeDetailQuery.data.buyer_shipping_free),
      hidden_price_mode: feeDetailQuery.data.hidden_price_mode ?? '',
      hidden_price_value: feeDetailQuery.data.hidden_price_value == null ? '' : String(feeDetailQuery.data.hidden_price_value),
      is_default: feeDetailQuery.data.is_default === true,
      is_active: feeDetailQuery.data.is_active !== false,
      metadata_text: toJsonText(feeDetailQuery.data.metadata),
    });
    setFeeMessage('');
  }, [feeDetailQuery.data]);

  const shippingMutation = useMutation({
    mutationFn: () => {
      if (!selectedKey || !shippingForm) {
        throw new Error('请先选择一条物流模板');
      }
      return updateShippingProfile(selectedKey, {
        profile_name: shippingForm.profile_name.trim(),
        market_code: shippingForm.market_code.trim(),
        site_code: shippingForm.site_code.trim(),
        channel_name: shippingForm.channel_name.trim(),
        currency: shippingForm.currency.trim(),
        chargeable_weight_mode: shippingForm.chargeable_weight_mode.trim(),
        weight_rounding_mode: shippingForm.weight_rounding_mode.trim() || null,
        weight_rounding_base_g: parseNullableNumber(shippingForm.weight_rounding_base_g, '重量取整基数'),
        volumetric_divisor: parseNullableNumber(shippingForm.volumetric_divisor, '体积重除数'),
        first_weight_g: parseNullableNumber(shippingForm.first_weight_g, '首重克数'),
        first_weight_fee: parseNullableNumber(shippingForm.first_weight_fee, '首重费用'),
        continue_weight_g: parseNullableNumber(shippingForm.continue_weight_g, '续重克数'),
        continue_weight_fee: parseNullableNumber(shippingForm.continue_weight_fee, '续重费用'),
        max_weight_g: parseNullableNumber(shippingForm.max_weight_g, '最大重量'),
        shipping_subsidy_rule_type: shippingForm.shipping_subsidy_rule_type.trim() || null,
        hidden_shipping_formula: shippingForm.hidden_shipping_formula.trim() || null,
        hidden_shipping_continue_fee: parseNullableNumber(shippingForm.hidden_shipping_continue_fee, '隐藏续重费'),
        platform_shipping_fee_rate: parseNullableNumber(shippingForm.platform_shipping_fee_rate, '平台运费费率'),
        platform_shipping_fee_cap: parseNullableNumber(shippingForm.platform_shipping_fee_cap, '平台运费封顶'),
        is_default: shippingForm.is_default,
        is_active: shippingForm.is_active,
        subsidy_rules_json: parseJsonValue(shippingForm.subsidy_rules_text, '运费补贴规则'),
        metadata: parseJsonObject(shippingForm.metadata_text, '物流模板元数据'),
      });
    },
    onSuccess: async (response) => {
      setShippingMessage(response.message);
      await queryClient.invalidateQueries({ queryKey: ['shipping-profiles'] });
    },
    onError: (error) => {
      setShippingMessage(error instanceof Error ? error.message : '保存失败');
    },
  });

  const feeMutation = useMutation({
    mutationFn: () => {
      if (!feeProfileCode || !feeForm) {
        throw new Error('请先选择关联利润规则');
      }
      return updateFeeProfile(feeProfileCode, {
        profile_name: feeForm.profile_name.trim(),
        market_code: feeForm.market_code.trim() || null,
        site_code: feeForm.site_code.trim(),
        currency: feeForm.currency.trim() || null,
        commission_rate: parseNullableNumber(feeForm.commission_rate, '佣金率'),
        transaction_fee_rate: parseNullableNumber(feeForm.transaction_fee_rate, '交易手续费率'),
        pre_sale_service_rate: parseNullableNumber(feeForm.pre_sale_service_rate, '预售服务费率'),
        tax_rate: parseNullableNumber(feeForm.tax_rate, '税费率'),
        agent_fee_cny: parseNullableNumber(feeForm.agent_fee_cny, '货代费'),
        commission_free_days: parseNullableNumber(feeForm.commission_free_days, '免佣天数'),
        buyer_shipping_ordinary: parseNullableNumber(feeForm.buyer_shipping_ordinary, '普通买家运费'),
        buyer_shipping_discount: parseNullableNumber(feeForm.buyer_shipping_discount, '折扣买家运费'),
        buyer_shipping_free: parseNullableNumber(feeForm.buyer_shipping_free, '免运买家运费'),
        hidden_price_mode: feeForm.hidden_price_mode.trim() || null,
        hidden_price_value: parseNullableNumber(feeForm.hidden_price_value, '藏价值'),
        is_default: feeForm.is_default,
        is_active: feeForm.is_active,
        metadata: parseJsonObject(feeForm.metadata_text, '利润规则元数据'),
      });
    },
    onSuccess: async (response) => {
      setFeeMessage(response.message);
      await queryClient.invalidateQueries({ queryKey: ['fee-profiles'] });
    },
    onError: (error) => {
      setFeeMessage(error instanceof Error ? error.message : '保存失败');
    },
  });

  const activeCount = useMemo(() => (listQuery.data?.items ?? []).filter((item) => item.is_active !== false).length, [listQuery.data]);

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Shipping + Profit</span>
          <h1>物流与利润</h1>
          <p>物流模板和利润规则统一维护，费用默认值与免佣期已完成初始化。</p>
        </div>
        <div className="agent-list-card">
          <div className="section-head compact"><h2>筛选</h2><span>{listQuery.data?.total ?? 0}</span></div>
          <div className="filter-stack">
            <input className="filter-input" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索编码 / 名称 / 站点" />
            <input className="filter-input" value={siteCode} onChange={(event) => setSiteCode(event.target.value)} placeholder="site_code，例如 shopee_tw" />
            <label className="inline-checkbox"><input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} />显示停用配置</label>
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Config Center</span>
            <h2>物流计费 + 利润费率</h2>
            <p>左边选物流模板，右边同时维护物流参数和站点利润规则，不再拆两张配置页来回切换。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">shipping</span>
            <span className="status-pill success">fee-rules</span>
          </div>
        </section>

        <section className="metrics-grid page-metrics-grid">
          <div className="metric-card"><span className="metric-label">记录总数</span><strong className="metric-value" data-accent="blue">{listQuery.data?.total ?? 0}</strong></div>
          <div className="metric-card"><span className="metric-label">启用中</span><strong className="metric-value" data-accent="green">{activeCount}</strong></div>
          <div className="metric-card"><span className="metric-label">当前会话</span><strong className="metric-value" data-accent="amber">{session.user?.display_name ?? '未登录'}</strong></div>
        </section>

        <section className="detail-layout">
          <ConfigListPanel<ShippingProfileListItem>
            title="物流模板"
            total={listQuery.data?.total ?? 0}
            primaryField="shipping_profile_code"
            secondaryField="site_code"
            emptyLabelField="profile_name"
            items={listQuery.data?.items ?? []}
            selectedKey={selectedKey}
            onSelect={setSelectedKey}
          />

          <div className="table-card list-surface">
            <div className="section-head"><h3>整合编辑</h3><span>{selectedKey ?? '未选择'}</span></div>
            {detailQuery.isLoading ? <PageState title="正在加载物流模板" detail="读取物流参数和关联利润规则。" /> : detailQuery.isError ? <PageState title="物流模板加载失败" detail={detailQuery.error instanceof Error ? detailQuery.error.message : 'unknown error'} /> : !detailQuery.data || !shippingForm ? <PageState title="暂无配置详情" detail="先从左侧选择一条物流模板。" /> : (
              <div className="panel-column">
                <ReadonlySummary title="物流模板摘要" data={detailQuery.data as BaseRecord} />
                <div className="record-item static">
                  <div className="section-head compact"><h3>物流模板</h3><span>{shippingMutation.isPending ? 'saving' : 'ready'}</span></div>
                  <div className="config-form-grid">
                    <label className="form-field"><span>模板名称</span><input className="filter-input" value={shippingForm.profile_name} onChange={(event) => setShippingForm((current) => current ? { ...current, profile_name: event.target.value } : current)} /></label>
                    <label className="form-field"><span>市场编码</span><input className="filter-input" value={shippingForm.market_code} onChange={(event) => setShippingForm((current) => current ? { ...current, market_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>站点编码</span><input className="filter-input" value={shippingForm.site_code} onChange={(event) => setShippingForm((current) => current ? { ...current, site_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>渠道名称</span><input className="filter-input" value={shippingForm.channel_name} onChange={(event) => setShippingForm((current) => current ? { ...current, channel_name: event.target.value } : current)} /></label>
                    <label className="form-field"><span>币种</span><input className="filter-input" value={shippingForm.currency} onChange={(event) => setShippingForm((current) => current ? { ...current, currency: event.target.value } : current)} /></label>
                    <label className="form-field"><span>计费模式</span><input className="filter-input" value={shippingForm.chargeable_weight_mode} onChange={(event) => setShippingForm((current) => current ? { ...current, chargeable_weight_mode: event.target.value } : current)} /></label>
                    <label className="form-field"><span>取整模式</span><input className="filter-input" value={shippingForm.weight_rounding_mode} onChange={(event) => setShippingForm((current) => current ? { ...current, weight_rounding_mode: event.target.value } : current)} /></label>
                    <label className="form-field"><span>取整基数(g)</span><input className="filter-input" value={shippingForm.weight_rounding_base_g} onChange={(event) => setShippingForm((current) => current ? { ...current, weight_rounding_base_g: event.target.value } : current)} /></label>
                    <label className="form-field"><span>体积重除数</span><input className="filter-input" value={shippingForm.volumetric_divisor} onChange={(event) => setShippingForm((current) => current ? { ...current, volumetric_divisor: event.target.value } : current)} /></label>
                    <label className="form-field"><span>首重(g)</span><input className="filter-input" value={shippingForm.first_weight_g} onChange={(event) => setShippingForm((current) => current ? { ...current, first_weight_g: event.target.value } : current)} /></label>
                    <label className="form-field"><span>首重费用</span><input className="filter-input" value={shippingForm.first_weight_fee} onChange={(event) => setShippingForm((current) => current ? { ...current, first_weight_fee: event.target.value } : current)} /></label>
                    <label className="form-field"><span>续重(g)</span><input className="filter-input" value={shippingForm.continue_weight_g} onChange={(event) => setShippingForm((current) => current ? { ...current, continue_weight_g: event.target.value } : current)} /></label>
                    <label className="form-field"><span>续重费用</span><input className="filter-input" value={shippingForm.continue_weight_fee} onChange={(event) => setShippingForm((current) => current ? { ...current, continue_weight_fee: event.target.value } : current)} /></label>
                    <label className="form-field"><span>最大重量(g)</span><input className="filter-input" value={shippingForm.max_weight_g} onChange={(event) => setShippingForm((current) => current ? { ...current, max_weight_g: event.target.value } : current)} /></label>
                    <label className="form-field"><span>补贴规则类型</span><input className="filter-input" value={shippingForm.shipping_subsidy_rule_type} onChange={(event) => setShippingForm((current) => current ? { ...current, shipping_subsidy_rule_type: event.target.value } : current)} /></label>
                    <label className="form-field form-field-full"><span>隐藏运费公式</span><input className="filter-input" value={shippingForm.hidden_shipping_formula} onChange={(event) => setShippingForm((current) => current ? { ...current, hidden_shipping_formula: event.target.value } : current)} /></label>
                    <label className="form-field"><span>隐藏续重费</span><input className="filter-input" value={shippingForm.hidden_shipping_continue_fee} onChange={(event) => setShippingForm((current) => current ? { ...current, hidden_shipping_continue_fee: event.target.value } : current)} /></label>
                    <label className="form-field"><span>平台运费费率</span><input className="filter-input" value={shippingForm.platform_shipping_fee_rate} onChange={(event) => setShippingForm((current) => current ? { ...current, platform_shipping_fee_rate: event.target.value } : current)} /></label>
                    <label className="form-field"><span>平台运费封顶</span><input className="filter-input" value={shippingForm.platform_shipping_fee_cap} onChange={(event) => setShippingForm((current) => current ? { ...current, platform_shipping_fee_cap: event.target.value } : current)} /></label>
                  </div>
                  <div className="config-toggle-grid">
                    <label className="inline-checkbox"><input type="checkbox" checked={shippingForm.is_default} onChange={(event) => setShippingForm((current) => current ? { ...current, is_default: event.target.checked } : current)} />默认模板</label>
                    <label className="inline-checkbox"><input type="checkbox" checked={shippingForm.is_active} onChange={(event) => setShippingForm((current) => current ? { ...current, is_active: event.target.checked } : current)} />启用模板</label>
                  </div>
                  <label className="form-field form-field-full config-section"><span>补贴规则 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={shippingForm.subsidy_rules_text} onChange={(event) => setShippingForm((current) => current ? { ...current, subsidy_rules_text: event.target.value } : current)} /></label>
                  <label className="form-field form-field-full config-section"><span>元数据 JSON</span><textarea className="form-textarea config-json-editor config-textarea-medium" value={shippingForm.metadata_text} onChange={(event) => setShippingForm((current) => current ? { ...current, metadata_text: event.target.value } : current)} /></label>
                  <div className="form-actions">
                    <button className="ghost-button" onClick={() => shippingMutation.mutate()} disabled={shippingMutation.isPending}>{shippingMutation.isPending ? '保存中...' : '保存物流模板'}</button>
                  </div>
                  {shippingMessage ? <div className="inline-meta config-save-message">{shippingMessage}</div> : null}
                </div>
                {feeDetailQuery.isLoading ? <PageState title="正在加载利润规则" detail="读取站点费率、免佣期和买家运费。" /> : feeDetailQuery.isError ? <PageState title="利润规则加载失败" detail={feeDetailQuery.error instanceof Error ? feeDetailQuery.error.message : 'unknown error'} /> : <FeeRulePanel feeProfileCode={feeProfileCode} feeDetail={feeDetailQuery.data} feeForm={feeForm} setFeeForm={setFeeForm} feePending={feeMutation.isPending} feeMessage={feeMessage} onSave={() => feeMutation.mutate()} />}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export function ConfigDebugToolsPage() {
  const { session } = useAuth();
  const [formState, setFormState] = useState<ProductDebugForm>({
    product_id_new: 'AL0001001260000068',
    market_code: 'shopee_tw',
    site_code: 'shopee_tw',
    content_policy_code: '',
    prompt_profile_code: '',
    shipping_profile_code: '',
    fee_profile_code: '',
    mode: 'title',
    target_profit_rate: '0.20',
  });
  const [promptResult, setPromptResult] = useState<PromptPreviewResponse | null>(null);
  const [profitResult, setProfitResult] = useState<ProfitTrialResponse | null>(null);
  const [message, setMessage] = useState('');

  const promptMutation = useMutation({
    mutationFn: () => generatePromptPreview({
      market_code: formState.market_code.trim() || null,
      site_code: formState.site_code.trim() || null,
      content_policy_code: formState.content_policy_code.trim() || null,
      prompt_profile_code: formState.prompt_profile_code.trim() || null,
      product_id_new: formState.product_id_new.trim(),
      mode: formState.mode,
    }),
    onSuccess: (response) => {
      setPromptResult(response);
      setMessage('Listing 预览已生成');
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : '生成失败');
    },
  });

  const profitMutation = useMutation({
    mutationFn: () => runProfitTrial({
      market_code: formState.market_code.trim() || null,
      site_code: formState.site_code.trim() || null,
      shipping_profile_code: formState.shipping_profile_code.trim() || null,
      fee_profile_code: formState.fee_profile_code.trim() || null,
      product_id_new: formState.product_id_new.trim(),
      target_profit_rate: Number(formState.target_profit_rate),
    }),
    onSuccess: (response) => {
      setProfitResult(response);
      setMessage('整商品利润试算已完成');
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : '试算失败');
    },
  });

  const listingJson = promptResult?.preview_json ?? promptResult;
  const profitJson = profitResult ?? null;

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Product Debug</span>
          <h1>调试面板</h1>
          <p>按商品主货号直接输出整商品 Listing JSON 和多 SKU 利润试算结果。</p>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Validation Lab</span>
            <h2>主货号级调试</h2>
            <p>输入主货号后，标题、描述、SKU 相关信息会按整商品聚合输出，不再要求逐个字段手填。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">listing-json</span>
            <span className="status-pill success">multi-sku</span>
          </div>
        </section>

        <section className="detail-layout">
          <div className="table-card list-surface">
            <div className="section-head"><h3>调试参数</h3><span>{session.user?.display_name ?? '未登录'}</span></div>
            <div className="config-form-grid">
              <label className="form-field"><span>商品主货号</span><input className="filter-input" value={formState.product_id_new} onChange={(event) => setFormState((current) => ({ ...current, product_id_new: event.target.value }))} /></label>
              <label className="form-field"><span>市场编码</span><input className="filter-input" value={formState.market_code} onChange={(event) => setFormState((current) => ({ ...current, market_code: event.target.value }))} /></label>
              <label className="form-field"><span>站点编码</span><input className="filter-input" value={formState.site_code} onChange={(event) => setFormState((current) => ({ ...current, site_code: event.target.value }))} /></label>
              <label className="form-field"><span>内容策略编码</span><input className="filter-input" value={formState.content_policy_code} onChange={(event) => setFormState((current) => ({ ...current, content_policy_code: event.target.value }))} /></label>
              <label className="form-field"><span>提示词模板编码</span><input className="filter-input" value={formState.prompt_profile_code} onChange={(event) => setFormState((current) => ({ ...current, prompt_profile_code: event.target.value }))} /></label>
              <label className="form-field"><span>物流模板编码</span><input className="filter-input" value={formState.shipping_profile_code} onChange={(event) => setFormState((current) => ({ ...current, shipping_profile_code: event.target.value }))} /></label>
              <label className="form-field"><span>利润规则编码</span><input className="filter-input" value={formState.fee_profile_code} onChange={(event) => setFormState((current) => ({ ...current, fee_profile_code: event.target.value }))} /></label>
              <label className="form-field"><span>Prompt 观测模式</span><select className="filter-select" value={formState.mode} onChange={(event) => setFormState((current) => ({ ...current, mode: event.target.value as ProductDebugForm['mode'] }))}><option value="title">title</option><option value="description">description</option><option value="sku">sku</option></select></label>
              <label className="form-field"><span>目标利润率</span><input className="filter-input" value={formState.target_profit_rate} onChange={(event) => setFormState((current) => ({ ...current, target_profit_rate: event.target.value }))} /></label>
            </div>
            <div className="form-actions">
              <button className="ghost-button" onClick={() => promptMutation.mutate()} disabled={!session.authenticated || promptMutation.isPending}>{promptMutation.isPending ? '生成中...' : '生成 Listing JSON'}</button>
              <button className="ghost-button" onClick={() => profitMutation.mutate()} disabled={!session.authenticated || profitMutation.isPending}>{profitMutation.isPending ? '试算中...' : '运行多 SKU 试算'}</button>
            </div>
            {message ? <div className="inline-meta config-save-message">{message}</div> : null}
          </div>

          <div className="table-card list-surface">
            <div className="section-head"><h3>Listing 结果 JSON</h3><span>{formState.product_id_new}</span></div>
            {listingJson ? <pre className="config-json-preview">{formatJson(listingJson)}</pre> : <PageState title="尚未生成 Listing 结果" detail="点击左侧按钮后，这里会输出整商品聚合 JSON。" />}
            {promptResult ? (
              <>
                <div className="section-head compact"><h3>Prompt 调试响应</h3><span>{promptResult.model?.name ?? promptResult.mode}</span></div>
                {promptResult.model ? <div className="inline-meta">模型：{promptResult.model.name}{promptResult.model.used_fallback ? '（fallback）' : ''}</div> : null}
                {promptResult.prompt_source ? <div className="inline-meta">模板来源：{promptResult.prompt_source}</div> : null}
                {promptResult.template_version ? <div className="inline-meta">模板版本：{promptResult.template_version}</div> : null}
                {promptResult.resolved?.listing_language ? <div className="inline-meta">上架语言：{promptResult.resolved.listing_language}</div> : null}
                <pre className="config-json-preview">{formatJson(promptResult)}</pre>
              </>
            ) : null}
          </div>

          <div className="table-card list-surface">
            <div className="section-head"><h3>利润试算 JSON</h3><span>{formState.product_id_new}</span></div>
            {profitJson ? <pre className="config-json-preview">{formatJson(profitJson)}</pre> : <PageState title="尚未生成利润试算" detail="运行试算后，这里会返回该商品下全部 SKU 的结果列表。" />}
          </div>
        </section>
      </main>
    </div>
  );
}

export function MarketConfigsPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState('');
  const [siteCode, setSiteCode] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [formState, setFormState] = useState<MarketConfigForm | null>(null);
  const [message, setMessage] = useState('');

  const listQuery = useQuery({
    queryKey: ['market-configs', 'list', keyword, siteCode, showInactive],
    queryFn: () => fetchMarketConfigs({ page: 1, pageSize: 100, keyword, siteCode, isActive: showInactive ? undefined : true }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!selectedKey && listQuery.data?.items?.length) {
      setSelectedKey(listQuery.data.items[0]?.market_code ?? null);
    }
  }, [listQuery.data, selectedKey]);

  const detailQuery = useQuery({
    queryKey: ['market-configs', 'detail', selectedKey],
    queryFn: () => fetchMarketConfig(selectedKey as string),
    enabled: selectedKey != null,
  });

  useEffect(() => {
    if (!detailQuery.data) {
      return;
    }
    setFormState({
      config_name: detailQuery.data.config_name ?? '',
      channel_code: detailQuery.data.channel_code ?? '',
      site_code: detailQuery.data.site_code ?? '',
      default_currency: detailQuery.data.default_currency ?? '',
      source_language: detailQuery.data.source_language ?? '',
      listing_language: detailQuery.data.listing_language ?? '',
      default_shipping_profile_code: detailQuery.data.default_shipping_profile_code ?? '',
      default_content_policy_code: detailQuery.data.default_content_policy_code ?? '',
      default_fee_profile_code: detailQuery.data.default_fee_profile_code ?? '',
      commission_free_days: detailQuery.data.commission_free_days == null ? '' : String(detailQuery.data.commission_free_days),
      default_erp_profile_code: detailQuery.data.default_erp_profile_code ?? '',
      default_category_profile_code: detailQuery.data.default_category_profile_code ?? '',
      default_price_policy_code: detailQuery.data.default_price_policy_code ?? '',
      allow_publish: detailQuery.data.allow_publish !== false,
      allow_profit_analysis: detailQuery.data.allow_profit_analysis !== false,
      allow_listing_optimization: detailQuery.data.allow_listing_optimization !== false,
      is_active: detailQuery.data.is_active !== false,
      effective_from: toDatetimeLocalValue(detailQuery.data.effective_from),
      effective_to: toDatetimeLocalValue(detailQuery.data.effective_to),
      metadata_text: toJsonText(detailQuery.data.metadata),
    });
    setMessage('');
  }, [detailQuery.data]);

  const mutation = useMutation({
    mutationFn: () => {
      if (!selectedKey || !formState) {
        throw new Error('请先选择一条市场配置');
      }
      return updateMarketConfig(selectedKey, {
        config_name: formState.config_name.trim(),
        channel_code: formState.channel_code.trim(),
        site_code: formState.site_code.trim(),
        default_currency: formState.default_currency.trim(),
        source_language: formState.source_language.trim(),
        listing_language: formState.listing_language.trim(),
        default_shipping_profile_code: formState.default_shipping_profile_code.trim() || null,
        default_content_policy_code: formState.default_content_policy_code.trim() || null,
        default_fee_profile_code: formState.default_fee_profile_code.trim() || null,
        commission_free_days: parseNullableNumber(formState.commission_free_days, '免佣天数'),
        default_erp_profile_code: formState.default_erp_profile_code.trim() || null,
        default_category_profile_code: formState.default_category_profile_code.trim() || null,
        default_price_policy_code: formState.default_price_policy_code.trim() || null,
        allow_publish: formState.allow_publish,
        allow_profit_analysis: formState.allow_profit_analysis,
        allow_listing_optimization: formState.allow_listing_optimization,
        is_active: formState.is_active,
        effective_from: fromDatetimeLocalValue(formState.effective_from),
        effective_to: fromDatetimeLocalValue(formState.effective_to),
        metadata: parseJsonObject(formState.metadata_text, '市场元数据'),
      });
    },
    onSuccess: async (response) => {
      setMessage(response.message);
      await queryClient.invalidateQueries({ queryKey: ['market-configs'] });
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : '保存失败');
    },
  });

  const activeCount = useMemo(
    () => (listQuery.data?.items ?? []).filter((item) => item.is_active !== false).length,
    [listQuery.data],
  );

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Market Configs</span>
          <h1>市场配置</h1>
          <p>管理 site_code 对应的默认货币、语言、默认 profile 绑定和能力开关。</p>
        </div>
        <div className="agent-list-card">
          <div className="section-head compact">
            <h2>筛选</h2>
            <span>{listQuery.data?.total ?? 0}</span>
          </div>
          <div className="filter-stack">
            <input className="filter-input" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索编码 / 名称 / 站点" />
            <input className="filter-input" value={siteCode} onChange={(event) => setSiteCode(event.target.value)} placeholder="site_code，例如 shopee_tw" />
            <label className="inline-checkbox">
              <input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} />
              显示停用配置
            </label>
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Config Center</span>
            <h2>市场配置</h2>
            <p>当前版本聚焦运营常改字段，右侧表单直接映射站点默认语言、币种、profile 绑定和能力开关。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">seed-ready</span>
            <span className="status-pill success">field-form</span>
          </div>
        </section>

        <section className="metrics-grid page-metrics-grid">
          <div className="metric-card">
            <span className="metric-label">记录总数</span>
            <strong className="metric-value" data-accent="blue">{listQuery.data?.total ?? 0}</strong>
          </div>
          <div className="metric-card">
            <span className="metric-label">启用中</span>
            <strong className="metric-value" data-accent="green">{activeCount}</strong>
          </div>
          <div className="metric-card">
            <span className="metric-label">当前会话</span>
            <strong className="metric-value" data-accent="amber">{session.user?.display_name ?? '未登录'}</strong>
          </div>
        </section>

        <section className="detail-layout">
          <ConfigListPanel<MarketConfigListItem>
            title="配置列表"
            total={listQuery.data?.total ?? 0}
            primaryField="market_code"
            secondaryField="site_code"
            emptyLabelField="config_name"
            items={listQuery.data?.items ?? []}
            selectedKey={selectedKey}
            onSelect={setSelectedKey}
          />

          <div className="table-card list-surface">
            <div className="section-head">
              <h3>详情与编辑</h3>
              <span>{selectedKey ?? '未选择'}</span>
            </div>
            {detailQuery.isLoading ? (
              <PageState title="正在加载配置详情" detail="读取完整字段与配置内容。" />
            ) : detailQuery.isError ? (
              <PageState title="配置详情加载失败" detail={detailQuery.error instanceof Error ? detailQuery.error.message : 'unknown error'} />
            ) : !detailQuery.data || !formState ? (
              <PageState title="暂无配置详情" detail="先从左侧选择一条市场配置。" />
            ) : (
              <div className="panel-column">
                <ReadonlySummary title="市场配置摘要" data={detailQuery.data as BaseRecord} />
                <div className="record-item static">
                  <div className="section-head compact">
                    <h3>运营表单</h3>
                    <span>{mutation.isPending ? 'saving' : 'ready'}</span>
                  </div>
                  <div className="config-form-grid">
                    <label className="form-field"><span>配置名称</span><input className="filter-input" value={formState.config_name} onChange={(event) => setFormState((current) => current ? { ...current, config_name: event.target.value } : current)} /></label>
                    <label className="form-field"><span>渠道编码</span><input className="filter-input" value={formState.channel_code} onChange={(event) => setFormState((current) => current ? { ...current, channel_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>站点编码</span><input className="filter-input" value={formState.site_code} onChange={(event) => setFormState((current) => current ? { ...current, site_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>默认币种</span><input className="filter-input" value={formState.default_currency} onChange={(event) => setFormState((current) => current ? { ...current, default_currency: event.target.value } : current)} /></label>
                    <label className="form-field"><span>源语言</span><input className="filter-input" value={formState.source_language} onChange={(event) => setFormState((current) => current ? { ...current, source_language: event.target.value } : current)} /></label>
                    <label className="form-field"><span>上架语言</span><input className="filter-input" value={formState.listing_language} onChange={(event) => setFormState((current) => current ? { ...current, listing_language: event.target.value } : current)} /></label>
                    <label className="form-field"><span>默认物流模板</span><input className="filter-input" value={formState.default_shipping_profile_code} onChange={(event) => setFormState((current) => current ? { ...current, default_shipping_profile_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>默认内容策略</span><input className="filter-input" value={formState.default_content_policy_code} onChange={(event) => setFormState((current) => current ? { ...current, default_content_policy_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>默认费率模板</span><input className="filter-input" value={formState.default_fee_profile_code} onChange={(event) => setFormState((current) => current ? { ...current, default_fee_profile_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>免佣天数</span><input className="filter-input" value={formState.commission_free_days} onChange={(event) => setFormState((current) => current ? { ...current, commission_free_days: event.target.value } : current)} /></label>
                    <label className="form-field"><span>默认 ERP 模板</span><input className="filter-input" value={formState.default_erp_profile_code} onChange={(event) => setFormState((current) => current ? { ...current, default_erp_profile_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>默认类目模板</span><input className="filter-input" value={formState.default_category_profile_code} onChange={(event) => setFormState((current) => current ? { ...current, default_category_profile_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>默认定价策略</span><input className="filter-input" value={formState.default_price_policy_code} onChange={(event) => setFormState((current) => current ? { ...current, default_price_policy_code: event.target.value } : current)} /></label>
                    <label className="form-field"><span>生效开始</span><input className="filter-input" type="datetime-local" value={formState.effective_from} onChange={(event) => setFormState((current) => current ? { ...current, effective_from: event.target.value } : current)} /></label>
                    <label className="form-field"><span>生效结束</span><input className="filter-input" type="datetime-local" value={formState.effective_to} onChange={(event) => setFormState((current) => current ? { ...current, effective_to: event.target.value } : current)} /></label>
                  </div>
                  <div className="config-toggle-grid">
                    <label className="inline-checkbox"><input type="checkbox" checked={formState.allow_publish} onChange={(event) => setFormState((current) => current ? { ...current, allow_publish: event.target.checked } : current)} />允许发布</label>
                    <label className="inline-checkbox"><input type="checkbox" checked={formState.allow_profit_analysis} onChange={(event) => setFormState((current) => current ? { ...current, allow_profit_analysis: event.target.checked } : current)} />允许利润分析</label>
                    <label className="inline-checkbox"><input type="checkbox" checked={formState.allow_listing_optimization} onChange={(event) => setFormState((current) => current ? { ...current, allow_listing_optimization: event.target.checked } : current)} />允许标题优化</label>
                    <label className="inline-checkbox"><input type="checkbox" checked={formState.is_active} onChange={(event) => setFormState((current) => current ? { ...current, is_active: event.target.checked } : current)} />启用配置</label>
                  </div>
                  <label className="form-field form-field-full config-section">
                    <span>市场元数据 JSON</span>
                    <textarea className="form-textarea config-json-editor config-textarea-medium" value={formState.metadata_text} onChange={(event) => setFormState((current) => current ? { ...current, metadata_text: event.target.value } : current)} />
                  </label>
                  <div className="form-actions">
                    <button className="ghost-button" onClick={() => detailQuery.data && setFormState({
                      config_name: detailQuery.data.config_name ?? '',
                      channel_code: detailQuery.data.channel_code ?? '',
                      site_code: detailQuery.data.site_code ?? '',
                      default_currency: detailQuery.data.default_currency ?? '',
                      source_language: detailQuery.data.source_language ?? '',
                      listing_language: detailQuery.data.listing_language ?? '',
                      default_shipping_profile_code: detailQuery.data.default_shipping_profile_code ?? '',
                      default_content_policy_code: detailQuery.data.default_content_policy_code ?? '',
                      default_fee_profile_code: detailQuery.data.default_fee_profile_code ?? '',
                      commission_free_days: detailQuery.data.commission_free_days == null ? '' : String(detailQuery.data.commission_free_days),
                      default_erp_profile_code: detailQuery.data.default_erp_profile_code ?? '',
                      default_category_profile_code: detailQuery.data.default_category_profile_code ?? '',
                      default_price_policy_code: detailQuery.data.default_price_policy_code ?? '',
                      allow_publish: detailQuery.data.allow_publish !== false,
                      allow_profit_analysis: detailQuery.data.allow_profit_analysis !== false,
                      allow_listing_optimization: detailQuery.data.allow_listing_optimization !== false,
                      is_active: detailQuery.data.is_active !== false,
                      effective_from: toDatetimeLocalValue(detailQuery.data.effective_from),
                      effective_to: toDatetimeLocalValue(detailQuery.data.effective_to),
                      metadata_text: toJsonText(detailQuery.data.metadata),
                    })}>重置</button>
                    <button className="ghost-button" onClick={() => mutation.mutate()} disabled={!session.authenticated || mutation.isPending || !selectedKey}>{mutation.isPending ? '保存中...' : '保存配置'}</button>
                  </div>
                  {message ? <div className="inline-meta config-save-message">{message}</div> : null}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export function SiteListingsPage() {
  const [keyword, setKeyword] = useState('');
  const [siteCode, setSiteCode] = useState('');
  const [publishStatus, setPublishStatus] = useState('');
  const [syncStatus, setSyncStatus] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const listQuery = useQuery({
    queryKey: ['ops-site-listings', keyword, siteCode, publishStatus, syncStatus],
    queryFn: () => fetchOpsSiteListings({ page: 1, pageSize: 100, keyword, siteCode, publishStatus, syncStatus }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!selectedId && listQuery.data?.items?.length) {
      setSelectedId(Number(listQuery.data.items[0]?.id));
    }
  }, [listQuery.data, selectedId]);

  const detailQuery = useQuery({
    queryKey: ['ops-site-listings', 'detail', selectedId],
    queryFn: () => fetchOpsSiteListing(selectedId as number),
    enabled: selectedId != null,
  });

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Site Listings</span>
          <h1>站点 Listing</h1>
          <p>这是运行态验证页，用来确认某个商品在不同站点的派生配置、发布状态和同步状态是否正确生效。</p>
        </div>
        <div className="agent-list-card">
          <div className="section-head compact">
            <h2>筛选</h2>
            <span>{listQuery.data?.total ?? 0}</span>
          </div>
          <div className="filter-stack">
            <input className="filter-input" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索货源ID / 主货号 / 标题" />
            <input className="filter-input" value={siteCode} onChange={(event) => setSiteCode(event.target.value)} placeholder="site_code，例如 shopee_ph" />
            <input className="filter-input" value={publishStatus} onChange={(event) => setPublishStatus(event.target.value)} placeholder="publish_status，例如 published" />
            <input className="filter-input" value={syncStatus} onChange={(event) => setSyncStatus(event.target.value)} placeholder="sync_status，例如 pending" />
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Runtime Validation</span>
            <h2>站点派生结果验证</h2>
            <p>这里重点展示 `site_listings` 和它绑定的内容策略、物流模板、发布状态与错误信息，帮助前端直接验证多站点配置是否生效。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">readonly</span>
            <span className="status-pill warning">live-data</span>
          </div>
        </section>

        <section className="detail-layout">
          <div className="table-card list-surface">
            <div className="section-head">
              <h3>Listing 列表</h3>
              <span>{listQuery.data?.total ?? 0}</span>
            </div>
            {listQuery.isLoading ? (
              <PageState title="正在加载站点 Listing" detail="读取运行态派生记录。" />
            ) : listQuery.isError ? (
              <PageState title="站点 Listing 加载失败" detail={listQuery.error instanceof Error ? listQuery.error.message : 'unknown error'} />
            ) : (
              <div className="record-list">
                {(listQuery.data?.items ?? []).map((item) => (
                  <button key={String(item.id)} className={`record-item ${selectedId === Number(item.id) ? 'active' : ''}`} onClick={() => setSelectedId(Number(item.id))}>
                    <div className="record-item-head">
                      <strong>{String(item.alibaba_product_id ?? item.product_id_new ?? item.id)}</strong>
                      <span className={`status-pill ${item.publish_status === 'published' ? 'success' : 'warning'}`}>{String(item.publish_status ?? 'unknown')}</span>
                    </div>
                    <p>{String(item.listing_title ?? '')}</p>
                    <div className="inline-meta">{String(item.site_code ?? '')} · {String(item.shop_code ?? '')}</div>
                    <div className="inline-meta">content={String(item.content_policy_code ?? 'N/A')} · shipping={String(item.shipping_profile_code ?? 'N/A')}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="table-card list-surface">
            <div className="section-head">
              <h3>Listing 详情</h3>
              <span>{selectedId ?? '未选择'}</span>
            </div>
            {detailQuery.isLoading ? (
              <PageState title="正在加载 Listing 详情" detail="读取关联配置码、发布状态和错误信息。" />
            ) : detailQuery.isError ? (
              <PageState title="Listing 详情加载失败" detail={detailQuery.error instanceof Error ? detailQuery.error.message : 'unknown error'} />
            ) : !detailQuery.data ? (
              <PageState title="暂无 Listing 详情" detail="先从左侧选择一条站点 Listing。" />
            ) : (
              <div className="panel-column">
                <div className="key-value-grid">
                  <div><span className="metric-label">站点</span><strong>{String(detailQuery.data.site_code ?? 'N/A')}</strong></div>
                  <div><span className="metric-label">店铺</span><strong>{String(detailQuery.data.shop_code ?? 'N/A')}</strong></div>
                  <div><span className="metric-label">内容策略</span><strong>{String(detailQuery.data.content_policy_code ?? 'N/A')}</strong></div>
                  <div><span className="metric-label">物流模板</span><strong>{String(detailQuery.data.shipping_profile_code ?? 'N/A')}</strong></div>
                  <div><span className="metric-label">发布状态</span><strong>{String(detailQuery.data.publish_status ?? 'N/A')}</strong></div>
                  <div><span className="metric-label">同步状态</span><strong>{String(detailQuery.data.sync_status ?? 'N/A')}</strong></div>
                </div>
                <div className="record-item static">
                  <strong>完整 JSON</strong>
                  <pre className="config-json-preview">{formatJson(detailQuery.data)}</pre>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export function PromptProfilesPage() {
  return <ContentPromptConfigPage />;
}

export function FeeProfilesPage() {
  return <LogisticsProfitConfigPage />;
}
