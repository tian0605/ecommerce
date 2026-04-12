"""Minimal FastAPI app for the OpenClaw ops dashboard."""
from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import logging
import os
from pathlib import Path
import socket
from datetime import datetime
from typing import Any, Dict, cast
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, model_validator
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import close_connection_pool, get_connection, get_pool_stats
from .queries import (
    create_media_upload_ticket,
    delete_media_asset,
    fetch_agent,
    fetch_agent_components,
    fetch_agent_heartbeats,
    fetch_agent_logs,
    fetch_agent_metrics,
    fetch_agent_tasks,
    fetch_agents,
    fetch_dashboard_alerts,
    fetch_dashboard_overview,
    fetch_full_listing_recent_tasks,
    fetch_profit_analysis_items,
    fetch_profit_analysis_summary,
    fetch_profit_init_candidate_summary,
    fetch_profit_init_recent_tasks,
    fetch_profit_sync_recent_tasks,
    fetch_product,
    fetch_products,
    fetch_content_policies,
    fetch_content_policy,
    fetch_fee_profile,
    fetch_fee_profiles,
    fetch_market_config,
    fetch_market_configs,
    fetch_product_debug_snapshot,
    fetch_prompt_profile,
    fetch_prompt_profiles,
    fetch_shipping_profile,
    fetch_shipping_profiles,
    fetch_site_listing,
    fetch_site_listings,
    fetch_system_config,
    fetch_system_configs,
    fetch_system_config_summary,
    fetch_task,
    fetch_task_logs,
    get_media_asset_download_url,
    rollback_system_config_record,
    sort_media_assets,
    store_media_asset,
    update_product_fields,
    update_product_sku_fields,
    upsert_content_policy_record,
    upsert_fee_profile_record,
    upsert_market_config_record,
    upsert_prompt_profile_record,
    upsert_shipping_profile_record,
    upsert_system_config_record,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = WORKSPACE_ROOT / 'scripts'


logger = logging.getLogger('uvicorn.error')

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r'https?://.*',
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=settings.session_max_age_seconds,
    same_site='lax',
    session_cookie='ops_api_session',
)


def _as_dict(value: Any) -> Dict[str, Any]:
    return cast(Dict[str, Any], value) if isinstance(value, dict) else {}


@app.on_event('startup')
def on_startup() -> None:
    logger.info('Ops API startup complete. DB pool stats: %s', get_pool_stats())


@app.on_event('shutdown')
def on_shutdown() -> None:
    logger.info('Ops API shutdown requested. Final DB pool stats before close: %s', get_pool_stats())
    close_connection_pool()


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ProductUpdatePayload(BaseModel):
    optimized_title: str | None = Field(default=None, max_length=200)
    optimized_description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=40)


class ProductSkuUpdatePayload(BaseModel):
    shopee_sku_name: str | None = Field(default=None, max_length=30)


class SystemConfigUpdatePayload(BaseModel):
    environment: str = Field(default='prod', max_length=32)
    value: str | None = None
    value_masked: str | None = None
    description: str | None = None
    change_reason: str | None = None
    verify_after_save: bool = True


class OpsConfigListPayload(BaseModel):
    keyword: str | None = None
    site_code: str | None = None
    is_active: bool | None = None


class SiteListingsFilterPayload(BaseModel):
    keyword: str | None = None
    site_code: str | None = None
    publish_status: str | None = None
    sync_status: str | None = None


class MediaUploadRequestPayload(BaseModel):
    product_id: int = Field(gt=0)
    sku_id: int | None = Field(default=None, gt=0)
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1)
    usage_type: str = Field(min_length=1, max_length=32)
    media_type: str = Field(default='image', min_length=1, max_length=32)


class MediaSortPayload(BaseModel):
    usage_type: str = Field(min_length=1, max_length=32)
    asset_ids: list[int] = Field(min_length=1)


class FullWorkflowPrecheckPayload(BaseModel):
    primary_url: str | None = None
    urls: list[str] = Field(default_factory=list)
    lightweight: bool = False
    publish: bool = True
    source: str | None = Field(default='ops-web', max_length=64)


class FullWorkflowTaskPayload(BaseModel):
    urls: list[str] = Field(min_length=1)
    lightweight: bool = False
    publish: bool = True
    site_codes: list[str] = Field(default_factory=list)
    market_code: str | None = Field(default=None, max_length=32)
    site_code: str | None = Field(default=None, max_length=32)
    shop_code: str | None = Field(default=None, max_length=64)
    source_language: str | None = Field(default=None, max_length=32)
    listing_language: str | None = Field(default=None, max_length=32)
    display_name: str | None = Field(default=None, max_length=120)
    expected_duration: int | None = Field(default=None, ge=5, le=1440)
    priority: str | None = Field(default='P1', max_length=8)
    note: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default='ops-web', max_length=64)


class ProfitSyncTaskPayload(BaseModel):
    alibaba_ids: list[str] = Field(min_length=1)
    profit_rate: float = Field(default=0.20, ge=0.01, le=0.9)
    market_code: str | None = Field(default=None, max_length=32)
    site_code: str | None = Field(default=None, max_length=32)
    display_name: str | None = Field(default=None, max_length=120)
    expected_duration: int | None = Field(default=None, ge=5, le=1440)
    priority: str | None = Field(default='P1', max_length=8)
    note: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default='ops-web', max_length=64)


class ProfitInitTaskPayload(BaseModel):
    scope: str = Field(default='missing_only', max_length=32)
    site: str | None = Field(default='TW', max_length=16)
    site_code: str | None = Field(default=None, max_length=32)
    force_recalculate: bool = False
    profit_rate: float = Field(default=0.20, ge=0.01, le=0.9)
    batch_size: int = Field(default=20, ge=1, le=200)
    priority: str | None = Field(default='P1', max_length=8)
    note: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default='ops-web', max_length=64)


class PromptPreviewPayload(BaseModel):
    market_code: str | None = Field(default=None, max_length=64)
    site_code: str | None = Field(default=None, max_length=64)
    content_policy_code: str | None = Field(default=None, max_length=64)
    prompt_profile_code: str | None = Field(default=None, max_length=64)
    product_id_new: str | None = Field(default=None, max_length=64)
    mode: str = Field(default='title', max_length=32)
    source_title: str | None = Field(default=None, min_length=1, max_length=200)
    source_description: str | None = None
    sku_name: str | None = Field(default=None, max_length=120)
    package_length: float | None = None
    package_width: float | None = None
    package_height: float | None = None

    @model_validator(mode='after')
    def validate_input_mode(self) -> 'PromptPreviewPayload':
        if self.product_id_new:
            return self
        if not self.source_title:
            raise ValueError('source_title is required when product_id_new is not provided')
        return self


class ProfitTrialPayload(BaseModel):
    market_code: str | None = Field(default=None, max_length=64)
    site_code: str | None = Field(default=None, max_length=64)
    fee_profile_code: str | None = Field(default=None, max_length=64)
    shipping_profile_code: str | None = Field(default=None, max_length=64)
    product_id_new: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    sku_name: str | None = Field(default=None, min_length=1, max_length=120)
    price_cny: float | None = Field(default=None, gt=0)
    package_weight: float | None = Field(default=None, gt=0)
    package_length: float | None = Field(default=None, ge=0)
    package_width: float | None = Field(default=None, ge=0)
    package_height: float | None = Field(default=None, ge=0)
    target_profit_rate: float = Field(default=0.20, ge=0.01, le=0.9)

    @model_validator(mode='after')
    def validate_input_mode(self) -> 'ProfitTrialPayload':
        if self.product_id_new:
            return self
        missing_fields: list[str] = []
        if not self.title:
            missing_fields.append('title')
        if not self.sku_name:
            missing_fields.append('sku_name')
        if self.price_cny is None:
            missing_fields.append('price_cny')
        if self.package_weight is None:
            missing_fields.append('package_weight')
        if missing_fields:
            raise ValueError(
                'Missing required fields when product_id_new is not provided: '
                + ', '.join(missing_fields)
            )
        return self


def _resolve_requested_site(site: str | None = None, site_code: str | None = None, default: str = 'TW') -> str:
    preferred = (site_code or site or '').strip()
    return preferred or default


def _load_auth_users() -> list[Dict[str, Any]]:
    try:
        raw = json.loads(settings.auth_users_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError('OPS_API_AUTH_USERS_JSON is invalid JSON') from exc
    if not isinstance(raw, list):
        raise RuntimeError('OPS_API_AUTH_USERS_JSON must be a list')
    users: list[Dict[str, Any]] = []
    for item in cast(list[Any], raw):
        if isinstance(item, dict):
            users.append(cast(Dict[str, Any], item))
    return users


def _verify_pbkdf2_password(password_hash: str, password: str) -> bool:
    try:
        algorithm, iterations_text, salt_b64, digest_b64 = password_hash.split('$', 3)
    except ValueError:
        return False
    if algorithm != 'pbkdf2_sha256':
        return False
    salt = base64.urlsafe_b64decode(salt_b64 + '=' * (-len(salt_b64) % 4))
    expected = base64.urlsafe_b64decode(digest_b64 + '=' * (-len(digest_b64) % 4))
    actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations_text))
    return hmac.compare_digest(actual, expected)


def _serialize_session_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'username': str(user['username']),
        'display_name': str(user.get('display_name') or user['username']),
        'roles': list(user.get('roles') or []),
    }


def _get_session_user(request: Request) -> Dict[str, Any] | None:
    auth = request.session.get('auth')
    if not isinstance(auth, dict):
        return None
    auth_dict = cast(Dict[str, Any], auth)
    username = auth_dict.get('username')
    roles = auth_dict.get('roles')
    if not username or not isinstance(roles, list):
        return None
    return {
        'username': str(username),
        'display_name': str(auth_dict.get('display_name') or username),
        'roles': [str(role) for role in cast(list[Any], roles)],
    }


def _require_authenticated_user(request: Request) -> Dict[str, Any]:
    user = _get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail='请先登录')
    return user


def _require_any_role(user: Dict[str, Any], allowed_roles: set[str]) -> None:
    roles = {str(role).lower() for role in user.get('roles', [])}
    if not roles.intersection({role.lower() for role in allowed_roles}):
        raise HTTPException(status_code=403, detail='当前账号没有执行该操作的权限')


def _allowed_config_roles(secret_level: str | None) -> set[str]:
    mapping = {
        'masked': {'editor', 'operator', 'admin', 'owner'},
        'secret': {'operator', 'admin', 'owner'},
        'critical': {'admin', 'owner'},
    }
    return mapping.get(str(secret_level or 'masked'), mapping['masked'])


def _validate_config_payload(payload: SystemConfigUpdatePayload, config_item: Dict[str, Any]) -> None:
    has_value = bool(payload.value and payload.value.strip())
    has_description_change = payload.description is not None and payload.description != config_item.get('description')
    if not has_value and not has_description_change:
        raise HTTPException(status_code=422, detail='至少修改值或说明后再保存')
    if config_item.get('is_required') and not has_value and config_item.get('value_masked') in (None, '', '未配置'):
        raise HTTPException(status_code=422, detail='必填配置当前无值，必须提供新值')
    if str(config_item.get('secret_level') or 'masked') != 'masked' and not (payload.change_reason or '').strip():
        raise HTTPException(status_code=422, detail='敏感配置变更必须填写变更原因')


def _validate_media_request(payload: MediaUploadRequestPayload, product: Dict[str, Any] | None) -> None:
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    if not payload.content_type.startswith('image/'):
        raise HTTPException(status_code=422, detail='当前仅支持图片上传')
    if payload.usage_type not in {'main_image', 'sku_image'}:
        raise HTTPException(status_code=422, detail='usage_type 仅支持 main_image 或 sku_image')
    if payload.usage_type == 'sku_image' and payload.sku_id is None:
        raise HTTPException(status_code=422, detail='SKU 图片必须指定 sku_id')


def _auth_response(user: Dict[str, Any] | None) -> Dict[str, Any]:
    return {'authenticated': user is not None, 'user': user}


def _create_task_manager() -> Any:
    module_path = SCRIPTS_ROOT / 'task_manager.py'
    spec = importlib.util.spec_from_file_location('ops_task_manager', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载 task_manager.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TaskManager()


def _load_multisite_module() -> Any:
    module_path = SCRIPTS_ROOT / 'multisite_config.py'
    spec = importlib.util.spec_from_file_location('ops_multisite_config', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载 multisite_config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_listing_optimizer_module() -> Any:
    module_path = WORKSPACE_ROOT / 'skills' / 'listing-batch-optimizer' / 'scripts' / 'listing_batch_optimizer.py'
    spec = importlib.util.spec_from_file_location('ops_listing_batch_optimizer', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载 listing_batch_optimizer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_profit_analyzer_module() -> Any:
    module_path = WORKSPACE_ROOT / 'skills' / 'profit-analyzer' / 'analyzer.py'
    spec = importlib.util.spec_from_file_location('ops_profit_analyzer', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载 profit analyzer')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_task_site_context(payload: Dict[str, Any] | None = None) -> Dict[str, str]:
    module = _load_multisite_module()
    normalize = getattr(module, 'normalize_site_context')
    return normalize(payload or {})


def _legacy_site_label(site_code: str | None) -> str:
    normalized = str(site_code or '').strip().lower()
    if normalized == 'shopee_ph':
        return 'PH'
    return 'TW' if normalized == 'shopee_tw' else normalized.upper()


def _apply_bundle_overrides(
    bundle: Dict[str, Any],
    *,
    content_policy_code: str | None = None,
    prompt_profile_code: str | None = None,
    shipping_profile_code: str | None = None,
    fee_profile_code: str | None = None,
) -> Dict[str, Any]:
    if content_policy_code:
        config_item = fetch_content_policy(content_policy_code)
        if not config_item:
            raise HTTPException(status_code=404, detail='Content policy not found')
        bundle['content_policy'] = config_item
    if prompt_profile_code:
        config_item = fetch_prompt_profile(prompt_profile_code)
        if not config_item:
            raise HTTPException(status_code=404, detail='Prompt profile not found')
        bundle['prompt_profile'] = config_item
    if shipping_profile_code:
        config_item = fetch_shipping_profile(shipping_profile_code)
        if not config_item:
            raise HTTPException(status_code=404, detail='Shipping profile not found')
        bundle['shipping_profile'] = config_item
    if fee_profile_code:
        config_item = fetch_fee_profile(fee_profile_code)
        if not config_item:
            raise HTTPException(status_code=404, detail='Fee profile not found')
        bundle['fee_profile'] = config_item
    return bundle


def _resolve_debug_product_or_404(product_id_new: str | None) -> Dict[str, Any]:
    product = fetch_product_debug_snapshot(str(product_id_new or '').strip()) if product_id_new else None
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    return product


def _build_listing_preview_json(optimizer: Any, product: Dict[str, Any], bundle: Dict[str, Any]) -> Dict[str, Any]:
    info = optimizer._extract_product_info(product)
    title = optimizer._generate_title(product, info, bundle)
    product_with_title = {**product, 'optimized_title': title}
    description = optimizer._generate_description(product_with_title, info, bundle)
    product_with_content = {
        **product_with_title,
        'optimized_description': description,
    }
    sku_rows = optimizer.build_sku_listing_names(product_with_content, bundle=bundle)
    return {
        'product_id_new': product.get('product_id_new'),
        'alibaba_product_id': product.get('alibaba_product_id'),
        'title': title,
        'description': description,
        'sku_count': len(sku_rows),
        'skus': sku_rows,
        'source': {
            'title': product.get('title'),
            'description': product.get('description'),
        },
    }


def _collect_prompt_model_info(optimizer: Any) -> Dict[str, Any] | None:
    getter = getattr(optimizer, 'get_last_llm_call', None)
    if not callable(getter):
        return None
    llm_call = _as_dict(getter())
    model_name = str(llm_call.get('model') or '').strip()
    if not model_name:
        return None
    return {
        'name': model_name,
        'provider': llm_call.get('provider'),
        'used_fallback': bool(llm_call.get('used_fallback')),
        'success': bool(llm_call.get('success')),
    }


def _collect_prompt_trace(optimizer: Any) -> Dict[str, Any] | None:
    getter = getattr(optimizer, 'get_last_prompt_trace', None)
    if not callable(getter):
        return None
    trace = _as_dict(getter())
    return trace if trace else None


def _resolve_full_listing_site_contexts(payload: FullWorkflowTaskPayload) -> list[Dict[str, str]]:
    requested_site_codes = [str(item).strip() for item in payload.site_codes if str(item).strip()]
    if not requested_site_codes:
        requested_site_codes = [str(payload.site_code or '').strip() or 'shopee_tw']

    deduped: list[str] = []
    seen: set[str] = set()
    for item in requested_site_codes:
        normalized = _normalize_task_site_context({'site_code': item}).get('site_code') or 'shopee_tw'
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return [
        _normalize_task_site_context({
            'market_code': payload.market_code,
            'site_code': site_code,
            'shop_code': payload.shop_code,
            'source_language': payload.source_language,
            'listing_language': payload.listing_language,
        })
        for site_code in deduped
    ]


def _create_single_full_listing_task(
    tm: Any,
    *,
    user: Dict[str, Any],
    urls: list[str],
    payload: FullWorkflowTaskPayload,
    site_context: Dict[str, str],
    display_name: str,
) -> Dict[str, Any]:
    task_name = _make_auto_listing_task_name()
    expected_duration = payload.expected_duration or max(60, len(urls) * 12)
    first_url = urls[0]
    initial_checkpoint: Dict[str, Any] = {
        'current_step': '等待调度执行',
        'completed_steps': [],
        'output_data': {
            'url': first_url,
            'products': urls,
            'product_count': len(urls),
            'site_context': site_context,
            'site_code': site_context.get('site_code'),
        },
        'next_action': '等待 workflow_runner.py 执行',
        'url': first_url,
        'products': urls,
        'product_count': len(urls),
        'lightweight': payload.lightweight,
        'no_publish': not payload.publish,
        'full_workflow': True,
        'site_context': site_context,
        'site_code': site_context.get('site_code'),
        'source': payload.source or 'ops-web',
        'operator': user['display_name'],
        'note': payload.note or '',
    }
    description = (
        f'通过 ops-web 发起完整工作流上架，商品数={len(urls)}，首条URL={first_url}，'
        f'site_code={site_context.get("site_code")}'
    )
    success_criteria = '完整工作流成功完成，商品完成采集、落库、优化与回写'
    created = tm.create_temp_task(
        task_name=task_name,
        display_name=display_name,
        description=description,
        expected_duration=expected_duration,
        priority=payload.priority or 'P1',
        success_criteria=success_criteria,
        initial_checkpoint=initial_checkpoint,
        initial_stage='build',
        site_context=site_context,
    )
    if not created:
        raise HTTPException(status_code=409, detail='任务创建失败')
    tm.update_task(task_name, stage_owner=user['display_name'])
    return {
        'task_name': task_name,
        'site_context': site_context,
        'expected_duration': expected_duration,
    }


def _normalize_full_listing_urls(primary_url: str | None, urls: list[str]) -> list[str]:
    candidates: list[str] = []
    if primary_url and primary_url.strip():
        candidates.append(primary_url.strip())
    for raw in urls:
        if not raw:
            continue
        for line in str(raw).splitlines():
            normalized = line.strip()
            if normalized:
                candidates.append(normalized)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _validate_1688_urls(urls: list[str]) -> list[str]:
    if not urls:
        raise HTTPException(status_code=422, detail='请至少提供一个 1688 商品链接')
    invalid = [item for item in urls if '/offer/' not in item or not item.startswith('http')]
    if invalid:
        raise HTTPException(status_code=422, detail=f'存在无效的 1688 链接: {invalid[0]}')
    return urls


def _read_config_env() -> Dict[str, str]:
    env_path = WORKSPACE_ROOT / 'config' / 'config.env'
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def _check_tcp_open(host: str, port: int, timeout_seconds: float = 1.5) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_seconds)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _build_full_listing_precheck(urls: list[str], lightweight: bool, publish: bool) -> Dict[str, Any]:
    env_values = _read_config_env()
    checks: list[Dict[str, Any]] = []

    cookie_file = env_values.get('MIAOSHOU_COOKIES_FILE') or '/home/ubuntu/.openclaw/skills/miaoshou-collector/miaoshou_cookies.json'
    cookie_exists = Path(cookie_file).exists()
    checks.append({
        'key': 'cookies',
        'label': '妙手ERP Cookies',
        'status': 'passed' if cookie_exists else 'failed',
        'detail': 'Cookies 文件可用' if cookie_exists else '未找到 Cookies 文件',
        'hint': None if cookie_exists else '请先刷新或补齐 miaoshou_cookies.json',
        'observed_value': cookie_file,
    })

    ssh_port = int(env_values.get('SSH_TUNNEL_PORT', '8080') or '8080')
    ssh_ready = _check_tcp_open('127.0.0.1', ssh_port)
    checks.append({
        'key': 'ssh_tunnel',
        'label': 'SSH 隧道',
        'status': 'passed' if ssh_ready else 'failed',
        'detail': f'端口 {ssh_port} 可连接' if ssh_ready else f'端口 {ssh_port} 未监听',
        'hint': None if ssh_ready else '请确认 SSH 隧道已建立',
        'observed_value': f'127.0.0.1:{ssh_port}',
    })

    local_url = env_values.get('LOCAL_1688_URL', 'http://127.0.0.1:8080')
    local_health = False
    try:
        with urllib_request.urlopen(f'{local_url.rstrip("/")}/health', timeout=2.0) as response:
            local_health = response.status == 200
    except (urllib_error.URLError, TimeoutError, ValueError):
        local_health = False
    checks.append({
        'key': 'local_weight',
        'label': '本地1688服务',
        'status': 'passed' if local_health else ('warning' if lightweight else 'failed'),
        'detail': '健康检查通过' if local_health else '健康检查失败',
        'hint': None if local_health else '请检查本地1688服务和 SSH 隧道',
        'observed_value': f'{local_url.rstrip("/")}/health',
    })

    postgres_ready = False
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT 1 AS ok')
            postgres_ready = bool(cur.fetchone())
    except Exception:
        postgres_ready = False
    checks.append({
        'key': 'postgres',
        'label': 'PostgreSQL',
        'status': 'passed' if postgres_ready else 'failed',
        'detail': '数据库连接正常' if postgres_ready else '数据库连接失败',
        'hint': None if postgres_ready else '请检查数据库连接与连接池状态',
        'observed_value': settings.db_name,
    })

    llm_ready = bool(env_values.get('LLM_API_KEY') or os.getenv('LLM_API_KEY'))
    checks.append({
        'key': 'llm_api',
        'label': 'LLM API',
        'status': 'passed' if llm_ready else 'warning',
        'detail': '已检测到 LLM API Key' if llm_ready else '未检测到 LLM API Key',
        'hint': None if llm_ready else '如需执行优化步骤，请检查 LLM 配置',
        'observed_value': 'configured' if llm_ready else None,
    })

    blocking_failed = any(item['status'] == 'failed' for item in checks)
    warning_only = not blocking_failed and any(item['status'] == 'warning' for item in checks)
    return {
        'status': 'error' if blocking_failed else ('warning' if warning_only else 'ok'),
        'checked_at': datetime.now().isoformat(),
        'summary': f'已检查 {len(checks)} 项前置条件',
        'checks': checks,
        'normalized': {
            'urls': urls,
            'product_count': len(urls),
            'lightweight': lightweight,
            'publish': publish,
        },
        'can_proceed': not blocking_failed,
    }


def _make_auto_listing_task_name() -> str:
    return f"AUTO-LISTING-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(2).hex()}"


def _make_profit_sync_task_name() -> str:
    return f"PROFIT-SYNC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(2).hex()}"


def _make_profit_init_task_name() -> str:
    return f"INIT-PROFIT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(2).hex()}"


def _normalize_alibaba_ids(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in items:
        for part in str(raw).replace('\n', ',').split(','):
            item = part.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            cleaned.append(item)
    if not cleaned:
        raise HTTPException(status_code=422, detail='请至少提供一个 1688 商品 ID')
    return cleaned


@app.get('/health')
def healthcheck() -> Dict[str, Any]:
    return {'status': 'ok', 'service': settings.app_name, 'version': settings.app_version}


@app.post('/workflow-tasks/full-listing/precheck')
def precheck_full_listing(payload: FullWorkflowPrecheckPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    urls = _validate_1688_urls(_normalize_full_listing_urls(payload.primary_url, payload.urls))
    return _build_full_listing_precheck(urls, payload.lightweight, payload.publish)


@app.post('/workflow-tasks/full-listing')
def create_full_listing_task(payload: FullWorkflowTaskPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    urls = _validate_1688_urls(_normalize_full_listing_urls(None, payload.urls))
    site_contexts = _resolve_full_listing_site_contexts(payload)
    base_display_name = payload.display_name or ('完整工作流上架' if len(urls) == 1 else f'完整工作流上架批次（{len(urls)}）')

    tm: Any = _create_task_manager()
    try:
        created_tasks: list[Dict[str, Any]] = []
        multisite = len(site_contexts) > 1
        for site_context in site_contexts:
            display_name = base_display_name
            if multisite:
                display_name = f"{base_display_name}-{_legacy_site_label(site_context.get('site_code'))}"
            created_tasks.append(
                _create_single_full_listing_task(
                    tm,
                    user=user,
                    urls=urls,
                    payload=payload,
                    site_context=site_context,
                    display_name=display_name,
                )
            )
    finally:
        tm.close()

    tasks = [fetch_task(item['task_name']) for item in created_tasks]
    return {
        'status': 'ok',
        'message': '完整工作流任务已创建',
        'task': tasks[0] if len(tasks) == 1 else None,
        'tasks': tasks,
        'launch_context': {
            'urls': urls,
            'product_count': len(urls),
            'lightweight': payload.lightweight,
            'publish': payload.publish,
            'site_contexts': site_contexts,
            'site_count': len(site_contexts),
            'expected_duration': max(item['expected_duration'] for item in created_tasks),
        },
    }


@app.post('/workflow-tasks/full-listing/{task_name}/retry')
def retry_full_listing_task(task_name: str, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    source_task = fetch_task(task_name)
    if not source_task:
        raise HTTPException(status_code=404, detail='Task not found')

    checkpoint_raw = source_task.get('progress_checkpoint')
    checkpoint = cast(Dict[str, Any], checkpoint_raw) if isinstance(checkpoint_raw, dict) else {}
    urls_raw = checkpoint.get('products') or ([checkpoint.get('url')] if checkpoint.get('url') else [])
    url_items = cast(list[Any], urls_raw) if isinstance(urls_raw, list) else []
    urls = _validate_1688_urls([str(item).strip() for item in url_items if str(item).strip()])
    checkpoint_site_context_raw = checkpoint.get('site_context')
    checkpoint_site_context = cast(Dict[str, Any], checkpoint_site_context_raw) if isinstance(checkpoint_site_context_raw, dict) else {}
    retry_payload = FullWorkflowTaskPayload(
        urls=urls,
        lightweight=bool(checkpoint.get('lightweight', False)),
        publish=not bool(checkpoint.get('no_publish', False)),
        market_code=str(checkpoint_site_context.get('market_code') or '') or None,
        site_code=str(checkpoint_site_context.get('site_code') or '') or None,
        shop_code=str(checkpoint_site_context.get('shop_code') or '') or None,
        source_language=str(checkpoint_site_context.get('source_language') or '') or None,
        listing_language=str(checkpoint_site_context.get('listing_language') or '') or None,
        display_name=f"重试-{source_task.get('display_name') or source_task.get('task_name')}",
        expected_duration=None,
        priority=str(source_task.get('priority') or 'P1'),
        note=f"retry_from={source_task.get('task_name')}",
        source='ops-web',
    )
    return create_full_listing_task(retry_payload, request)


@app.get('/workflow-tasks/full-listing/recent')
def get_recent_full_listing_tasks(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    exec_state: str | None = None,
    priority: str | None = None,
    lightweight: bool | None = None,
    publish: bool | None = None,
    keyword: str | None = None,
):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_full_listing_recent_tasks(
        page=page,
        page_size=page_size,
        exec_state=exec_state,
        priority=priority,
        lightweight=lightweight,
        publish=publish,
        keyword=keyword,
    )


@app.get('/profit-analysis/summary')
def get_profit_analysis_summary(request: Request, site: str | None = None, site_code: str | None = None) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_profit_analysis_summary(site=_resolve_requested_site(site=site, site_code=site_code, default=''))


@app.get('/profit-analysis/init/candidates/summary')
def get_profit_init_candidate_summary(request: Request, site: str | None = None, site_code: str | None = None) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_profit_init_candidate_summary(site=_resolve_requested_site(site=site, site_code=site_code, default=''))


@app.get('/profit-analysis/items')
def get_profit_analysis_items(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    site: str | None = None,
    site_code: str | None = None,
    profit_rate_min: float | None = None,
    profit_rate_max: float | None = None,
) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_profit_analysis_items(
        page=page,
        page_size=page_size,
        keyword=keyword,
        site=_resolve_requested_site(site=site, site_code=site_code, default=''),
        profit_rate_min=profit_rate_min,
        profit_rate_max=profit_rate_max,
    )


@app.post('/profit-analysis/sync')
def create_profit_sync_task(payload: ProfitSyncTaskPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    alibaba_ids = _normalize_alibaba_ids(payload.alibaba_ids)
    task_name = _make_profit_sync_task_name()
    display_name = payload.display_name or ('利润同步' if len(alibaba_ids) == 1 else f'利润同步批次（{len(alibaba_ids)}）')
    expected_duration = payload.expected_duration or max(30, len(alibaba_ids) * 4)
    site_context = _normalize_task_site_context({
        'market_code': payload.market_code,
        'site_code': payload.site_code,
    })
    initial_checkpoint: Dict[str, Any] = {
        'current_step': '等待利润同步调度',
        'completed_steps': [],
        'output_data': {
            'alibaba_ids': alibaba_ids,
            'product_count': len(alibaba_ids),
            'profit_rate': payload.profit_rate,
            'site_context': site_context,
            'site_code': site_context.get('site_code'),
        },
        'next_action': '等待 run_profit_analysis_sync.py 执行',
        'alibaba_ids': alibaba_ids,
        'product_count': len(alibaba_ids),
        'profit_rate': payload.profit_rate,
        'first_id': alibaba_ids[0],
        'site_context': site_context,
        'site_code': site_context.get('site_code'),
        'source': payload.source or 'ops-web',
        'operator': user['display_name'],
        'note': payload.note or '',
    }
    description = f"通过 ops-web 发起利润同步，商品数={len(alibaba_ids)}，首个ID={alibaba_ids[0]}"

    tm: Any = _create_task_manager()
    try:
        created = tm.create_temp_task(
            task_name=task_name,
            display_name=display_name,
            description=description,
            expected_duration=expected_duration,
            priority=payload.priority or 'P1',
            success_criteria='利润分析完成并同步飞书',
            initial_checkpoint=initial_checkpoint,
            initial_stage='build',
            site_context=site_context,
        )
        if not created:
            raise HTTPException(status_code=409, detail='利润同步任务创建失败')
        tm.update_task(task_name, stage_owner=user['display_name'])
    finally:
        tm.close()

    return {
        'status': 'ok',
        'message': '利润同步任务已创建',
        'task': fetch_task(task_name),
        'launch_context': {
            'alibaba_ids': alibaba_ids,
            'product_count': len(alibaba_ids),
            'profit_rate': payload.profit_rate,
            'site_context': site_context,
            'expected_duration': expected_duration,
        },
    }


@app.post('/profit-analysis/init')
def create_profit_init_task(payload: ProfitInitTaskPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})

    scope = (payload.scope or 'missing_only').strip().lower()
    if scope not in {'missing_only', 'all_products'}:
        raise HTTPException(status_code=422, detail='scope 仅支持 missing_only 或 all_products')

    site_context = _normalize_task_site_context({
        'site_code': payload.site_code or payload.site,
    })
    site = _legacy_site_label(site_context.get('site_code'))
    candidate_summary = fetch_profit_init_candidate_summary(site=site)
    candidate_count = int(candidate_summary.get('missing_products' if scope == 'missing_only' and not payload.force_recalculate else 'total_products') or 0)

    task_name = _make_profit_init_task_name()
    display_name = '利润明细初始化' if scope == 'all_products' else '利润明细缺口初始化'
    expected_duration = max(30, max(1, candidate_count) * 2)
    initial_checkpoint: Dict[str, Any] = {
        'current_step': '等待利润明细初始化调度',
        'completed_steps': [],
        'next_action': '等待 run_profit_analysis_init.py 执行',
        'scope': scope,
        'site': site,
        'site_code': site_context.get('site_code'),
        'site_context': site_context,
        'candidate_count': candidate_count,
        'batch_size': payload.batch_size,
        'force_recalculate': payload.force_recalculate,
        'profit_rate': payload.profit_rate,
        'source': payload.source or 'ops-web',
        'operator': user['display_name'],
        'note': payload.note or '',
        'output_data': {
            'scope': scope,
            'site': site,
            'site_code': site_context.get('site_code'),
            'candidate_count': candidate_count,
            'batch_size': payload.batch_size,
            'force_recalculate': payload.force_recalculate,
            'profit_rate': payload.profit_rate,
            'site_context': site_context,
        },
    }
    description = f"通过 ops-web 发起利润明细初始化，scope={scope}，site={site}，候选商品数={candidate_count}"

    tm: Any = _create_task_manager()
    try:
        created = tm.create_temp_task(
            task_name=task_name,
            display_name=display_name,
            description=description,
            expected_duration=expected_duration,
            priority=payload.priority or 'P1',
            success_criteria='补齐本地 product_analysis 明细',
            initial_checkpoint=initial_checkpoint,
            initial_stage='build',
            site_context=site_context,
        )
        if not created:
            raise HTTPException(status_code=409, detail='利润初始化任务创建失败')
        tm.update_task(task_name, stage_owner=user['display_name'])
    finally:
        tm.close()

    return {
        'status': 'ok',
        'message': '利润初始化任务已创建',
        'task': fetch_task(task_name),
        'launch_context': {
            'scope': scope,
            'site': site,
            'site_code': site_context.get('site_code'),
            'candidate_count': candidate_count,
            'batch_size': payload.batch_size,
            'force_recalculate': payload.force_recalculate,
            'profit_rate': payload.profit_rate,
            'expected_duration': expected_duration,
        },
    }


@app.post('/profit-analysis/init/{task_name}/retry')
def retry_profit_init_task(task_name: str, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    source_task = fetch_task(task_name)
    if not source_task:
        raise HTTPException(status_code=404, detail='Task not found')

    checkpoint_raw = source_task.get('progress_checkpoint')
    checkpoint_map = cast(Dict[str, Any], checkpoint_raw) if isinstance(checkpoint_raw, dict) else {}
    output_data_raw = checkpoint_map.get('output_data')
    output_data_map = cast(Dict[str, Any], output_data_raw) if isinstance(output_data_raw, dict) else {}
    scope = str(checkpoint_map.get('scope') or output_data_map.get('scope') or 'missing_only').strip().lower()
    site = str(checkpoint_map.get('site') or output_data_map.get('site') or 'TW').strip().upper()
    site_code = str(checkpoint_map.get('site_code') or output_data_map.get('site_code') or '').strip() or None
    batch_size = int(checkpoint_map.get('batch_size') or output_data_map.get('batch_size') or 20)
    force_recalculate = bool(checkpoint_map.get('force_recalculate') or output_data_map.get('force_recalculate') or False)
    profit_rate = float(checkpoint_map.get('profit_rate') or output_data_map.get('profit_rate') or 0.20)

    retry_payload = ProfitInitTaskPayload(
        scope=scope,
        site=site,
        site_code=site_code,
        batch_size=batch_size,
        force_recalculate=force_recalculate,
        profit_rate=profit_rate,
        priority=str(source_task.get('priority') or 'P1'),
        note=f"retry_from={source_task.get('task_name')}",
        source='ops-web',
    )
    return create_profit_init_task(retry_payload, request)


@app.get('/profit-analysis/sync/recent')
def get_recent_profit_sync_tasks(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    exec_state: str | None = None,
    priority: str | None = None,
    keyword: str | None = None,
) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_profit_sync_recent_tasks(
        page=page,
        page_size=page_size,
        exec_state=exec_state,
        priority=priority,
        keyword=keyword,
    )


@app.get('/profit-analysis/init/recent')
def get_recent_profit_init_tasks(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    exec_state: str | None = None,
    priority: str | None = None,
    keyword: str | None = None,
) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_profit_init_recent_tasks(
        page=page,
        page_size=page_size,
        exec_state=exec_state,
        priority=priority,
        keyword=keyword,
    )


@app.get('/auth/me')
def auth_me(request: Request) -> Dict[str, Any]:
    return _auth_response(_get_session_user(request))


@app.post('/auth/login')
def auth_login(payload: LoginPayload, request: Request) -> Dict[str, Any]:
    for user in _load_auth_users():
        if str(user.get('username')) == payload.username and _verify_pbkdf2_password(str(user.get('password_hash') or ''), payload.password):
            session_user = _serialize_session_user(user)
            request.session.clear()
            request.session['auth'] = session_user
            return _auth_response(session_user)
    raise HTTPException(status_code=401, detail='用户名或密码错误')


@app.post('/auth/logout')
def auth_logout(request: Request) -> Dict[str, Any]:
    request.session.clear()
    return _auth_response(None)


@app.get('/agents')
def list_agents(page: int = 1, page_size: int = 50, status: str | None = None, type: str | None = None, keyword: str | None = None):
    return fetch_agents(page=page, page_size=page_size, status=status, agent_type=type, keyword=keyword)


@app.get('/agents/{agent_id}')
def get_agent(agent_id: int):
    agent = fetch_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail='Agent not found')
    return agent


@app.get('/agents/{agent_id}/components')
def get_agent_components(agent_id: int):
    return {'items': fetch_agent_components(agent_id)}


@app.get('/agents/{agent_id}/tasks')
def get_agent_tasks(
    agent_id: int,
    page: int = 1,
    page_size: int = 100,
    exec_state: str | None = None,
    status: str | None = None,
    task_type: str | None = None,
    priority: str | None = None,
    task_level: int | None = None,
    keyword: str | None = None,
    component_code: str | None = None,
):
    return fetch_agent_tasks(
        agent_id,
        page=page,
        page_size=page_size,
        exec_state=exec_state,
        status=status,
        task_type=task_type,
        priority=priority,
        task_level=task_level,
        keyword=keyword,
        component_code=component_code,
    )


@app.get('/agents/{agent_id}/logs')
def get_agent_logs(
    agent_id: int,
    page: int = 1,
    page_size: int = 200,
    task_name: str | None = None,
    run_status: str | None = None,
    log_type: str | None = None,
    component_code: str | None = None,
):
    return fetch_agent_logs(agent_id, page=page, page_size=page_size, task_name=task_name, run_status=run_status, log_type=log_type, component_code=component_code)


@app.get('/agents/{agent_id}/heartbeats')
def get_agent_heartbeats(agent_id: int, page: int = 1, page_size: int = 100, status: str | None = None):
    return fetch_agent_heartbeats(agent_id, page=page, page_size=page_size, status=status)


@app.get('/agents/{agent_id}/metrics')
def get_agent_metrics(agent_id: int, window: str = '24h'):
    return fetch_agent_metrics(agent_id, window=window)


@app.get('/dashboard/overview')
def get_overview():
    return fetch_dashboard_overview()


@app.get('/dashboard/alerts')
def get_alerts(limit: int = 50):
    return {'items': fetch_dashboard_alerts(limit=limit)}


@app.get('/products')
def list_products(
    page: int = 1,
    page_size: int = 24,
    keyword: str | None = None,
    status: str | None = None,
    quick_filter: str | None = None,
    site_filter: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    inventory_warning_only: bool = False,
    listing_only: bool = False,
):
    return fetch_products(
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        quick_filter=quick_filter,
        site_filter=site_filter,
        price_min=price_min,
        price_max=price_max,
        inventory_warning_only=inventory_warning_only,
        listing_only=listing_only,
    )


@app.get('/products/{product_id}')
def get_product(product_id: int):
    product = fetch_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    return product


@app.patch('/products/{product_id}')
def patch_product(product_id: int, payload: ProductUpdatePayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'editor', 'operator', 'admin', 'owner'})
    updated = update_product_fields(product_id, payload.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail='Product not found')
    return {'status': 'ok', 'product': updated, 'message': '商品已更新'}


@app.patch('/products/{product_id}/skus/{sku_id}')
def patch_product_sku(product_id: int, sku_id: int, payload: ProductSkuUpdatePayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'editor', 'operator', 'admin', 'owner'})
    updated = update_product_sku_fields(product_id, sku_id, payload.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail='Product SKU not found')
    return {'status': 'ok', 'product': updated, 'message': 'SKU 规格名称已更新'}


@app.patch('/products/{product_id}/media-assets/sort')
def patch_product_media_sort(product_id: int, payload: MediaSortPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    try:
        updated = sort_media_assets(product_id, payload.usage_type, payload.asset_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail='Product not found')
    return {'status': 'ok', 'product': updated, 'message': '媒体排序已更新'}


@app.delete('/products/{product_id}/media-assets/{asset_id}')
def remove_product_media_asset(product_id: int, asset_id: int, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    try:
        updated = delete_media_asset(product_id, asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail='Media asset not found')
    return {'status': 'ok', 'product': updated, 'message': '媒体已删除'}


@app.get('/system-configs/summary')
def get_system_config_summary():
    return fetch_system_config_summary()


@app.get('/ops-configs/market-configs')
def list_market_configs_endpoint(
    request: Request,
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_market_configs(page=page, page_size=page_size, keyword=keyword, site_code=site_code, is_active=is_active)


@app.get('/ops-configs/market-configs/{market_code}')
def get_market_config_endpoint(market_code: str, request: Request):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    config_item = fetch_market_config(market_code)
    if not config_item:
        raise HTTPException(status_code=404, detail='Market config not found')
    return config_item


@app.put('/ops-configs/market-configs/{market_code}')
def put_market_config_endpoint(market_code: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    updated = upsert_market_config_record(market_code, {**payload, 'updated_by': user['display_name']})
    if not updated:
        raise HTTPException(status_code=404, detail='Market config not found')
    return {'status': 'ok', 'config': updated, 'message': '市场配置已保存'}


@app.get('/ops-configs/shipping-profiles')
def list_shipping_profiles_endpoint(
    request: Request,
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_shipping_profiles(page=page, page_size=page_size, keyword=keyword, site_code=site_code, is_active=is_active)


@app.get('/ops-configs/shipping-profiles/{shipping_profile_code}')
def get_shipping_profile_endpoint(shipping_profile_code: str, request: Request):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    config_item = fetch_shipping_profile(shipping_profile_code)
    if not config_item:
        raise HTTPException(status_code=404, detail='Shipping profile not found')
    return config_item


@app.put('/ops-configs/shipping-profiles/{shipping_profile_code}')
def put_shipping_profile_endpoint(shipping_profile_code: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    updated = upsert_shipping_profile_record(shipping_profile_code, {**payload, 'updated_by': user['display_name']})
    if not updated:
        raise HTTPException(status_code=404, detail='Shipping profile not found')
    return {'status': 'ok', 'config': updated, 'message': '物流模板已保存'}


@app.get('/ops-configs/content-policies')
def list_content_policies_endpoint(
    request: Request,
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_content_policies(page=page, page_size=page_size, keyword=keyword, site_code=site_code, is_active=is_active)


@app.get('/ops-configs/content-policies/{content_policy_code}')
def get_content_policy_endpoint(content_policy_code: str, request: Request):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    config_item = fetch_content_policy(content_policy_code)
    if not config_item:
        raise HTTPException(status_code=404, detail='Content policy not found')
    return config_item


@app.put('/ops-configs/content-policies/{content_policy_code}')
def put_content_policy_endpoint(content_policy_code: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    updated = upsert_content_policy_record(content_policy_code, {**payload, 'updated_by': user['display_name']})
    if not updated:
        raise HTTPException(status_code=404, detail='Content policy not found')
    return {'status': 'ok', 'config': updated, 'message': '内容策略已保存'}


@app.get('/ops-configs/prompt-profiles')
def list_prompt_profiles_endpoint(
    request: Request,
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_prompt_profiles(page=page, page_size=page_size, keyword=keyword, site_code=site_code, is_active=is_active)


@app.get('/ops-configs/prompt-profiles/{prompt_profile_code}')
def get_prompt_profile_endpoint(prompt_profile_code: str, request: Request):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    config_item = fetch_prompt_profile(prompt_profile_code)
    if not config_item:
        raise HTTPException(status_code=404, detail='Prompt profile not found')
    return config_item


@app.put('/ops-configs/prompt-profiles/{prompt_profile_code}')
def put_prompt_profile_endpoint(prompt_profile_code: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    updated = upsert_prompt_profile_record(prompt_profile_code, {**payload, 'updated_by': user['display_name']})
    if not updated:
        raise HTTPException(status_code=404, detail='Prompt profile not found')
    return {'status': 'ok', 'config': updated, 'message': '提示词模板已保存'}


@app.get('/ops-configs/fee-profiles')
def list_fee_profiles_endpoint(
    request: Request,
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_fee_profiles(page=page, page_size=page_size, keyword=keyword, site_code=site_code, is_active=is_active)


@app.get('/ops-configs/fee-profiles/{fee_profile_code}')
def get_fee_profile_endpoint(fee_profile_code: str, request: Request):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    config_item = fetch_fee_profile(fee_profile_code)
    if not config_item:
        raise HTTPException(status_code=404, detail='Fee profile not found')
    return config_item


@app.put('/ops-configs/fee-profiles/{fee_profile_code}')
def put_fee_profile_endpoint(fee_profile_code: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    updated = upsert_fee_profile_record(fee_profile_code, {**payload, 'updated_by': user['display_name']})
    if not updated:
        raise HTTPException(status_code=404, detail='Fee profile not found')
    return {'status': 'ok', 'config': updated, 'message': '利润规则已保存'}


@app.post('/ops-configs/prompt-preview')
def prompt_preview_endpoint(payload: PromptPreviewPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    try:
        module = _load_listing_optimizer_module()
        optimizer = module.ListingBatchOptimizer()
        try:
            bundle = optimizer._resolve_runtime_bundle({
                'market_code': payload.market_code,
                'site_code': payload.site_code,
            })
            bundle = _apply_bundle_overrides(
                bundle,
                content_policy_code=payload.content_policy_code,
                prompt_profile_code=payload.prompt_profile_code,
            )

            mode = payload.mode.strip().lower()
            if payload.product_id_new:
                product: Dict[str, Any] = {
                    **_resolve_debug_product_or_404(payload.product_id_new),
                    'market_code': payload.market_code,
                    'site_code': payload.site_code,
                }
                info = optimizer._extract_product_info(product)
                if mode == 'description':
                    title = optimizer._generate_title(product, info, bundle)
                    product_with_title: Dict[str, Any] = {**product, 'optimized_title': title}
                    description = optimizer._generate_description(product_with_title, info, bundle)
                    preview_json: Dict[str, Any] = {
                        'product_id_new': product.get('product_id_new'),
                        'alibaba_product_id': product.get('alibaba_product_id'),
                        'title': title,
                        'description': description,
                        'source': {
                            'title': product.get('title'),
                            'description': product.get('description'),
                        },
                    }
                    preview = str(description or '')
                elif mode == 'sku':
                    sku_rows = optimizer.build_sku_listing_names(product, bundle=bundle)
                    preview_json = {
                        'product_id_new': product.get('product_id_new'),
                        'alibaba_product_id': product.get('alibaba_product_id'),
                        'sku_count': len(sku_rows),
                        'skus': sku_rows,
                        'source': {
                            'title': product.get('title'),
                            'description': product.get('description'),
                        },
                    }
                    preview = json.dumps(sku_rows, ensure_ascii=False, indent=2)
                else:
                    title = optimizer._generate_title(product, info, bundle)
                    preview_json = {
                        'product_id_new': product.get('product_id_new'),
                        'alibaba_product_id': product.get('alibaba_product_id'),
                        'title': title,
                        'source': {
                            'title': product.get('title'),
                            'description': product.get('description'),
                        },
                    }
                    preview = str(title or '')
                prompt_trace = _collect_prompt_trace(optimizer) or {}
                bundle_site_context = _as_dict(bundle.get('site_context'))
                bundle_content_policy = _as_dict(bundle.get('content_policy'))
                bundle_prompt_profile = _as_dict(bundle.get('prompt_profile'))
                trace_resolved = _as_dict(prompt_trace.get('resolved'))
                return {
                    'status': 'ok',
                    'mode': mode,
                    'prompt': prompt_trace.get('prompt') or '',
                    'preview_text': preview,
                    'preview_json': preview_json,
                    'model': _collect_prompt_model_info(optimizer),
                    'prompt_source': prompt_trace.get('prompt_source'),
                    'template_version': prompt_trace.get('template_version'),
                    'rendered_variables': prompt_trace.get('rendered_variables'),
                    'resolved': {
                        'site_code': bundle_site_context.get('site_code'),
                        'listing_language': trace_resolved.get('listing_language') or bundle_site_context.get('listing_language'),
                        'content_policy_code': bundle_content_policy.get('content_policy_code'),
                        'prompt_profile_code': bundle_prompt_profile.get('prompt_profile_code'),
                        'product_id_new': product.get('product_id_new'),
                    },
                }

            if not payload.source_title:
                raise HTTPException(status_code=422, detail='source_title is required when product_id_new is not provided')

            product = cast(Dict[str, Any], {
                'title': payload.source_title,
                'description': payload.source_description or '',
                'optimized_title': payload.source_title,
                'optimized_description': payload.source_description or '',
                'skus': [{
                    'sku_name': payload.sku_name or '默认规格',
                    'name': payload.sku_name or '默认规格',
                    'package_length': payload.package_length,
                    'package_width': payload.package_width,
                    'package_height': payload.package_height,
                }],
            })
            info = optimizer._extract_product_info(product)
            if mode == 'description':
                preview = optimizer._generate_description(product, info, bundle)
                preview_json = {
                    'title': product.get('title'),
                    'description': preview,
                    'source': {
                        'title': product.get('title'),
                        'description': product.get('description'),
                    },
                }
            elif mode == 'sku':
                preview = optimizer._generate_sku_listing_name(product, cast(Dict[str, Any], product['skus'][0]), [], bundle=bundle)
                preview_json = {
                    'sku_count': 1,
                    'skus': [{
                        'sku_name': cast(Dict[str, Any], product['skus'][0]).get('sku_name'),
                        'shopee_sku_name': preview,
                    }],
                    'source': {
                        'title': product.get('title'),
                        'description': product.get('description'),
                    },
                }
            else:
                preview = optimizer._generate_title(product, info, bundle)
                preview_json = {
                    'title': preview,
                    'source': {
                        'title': product.get('title'),
                        'description': product.get('description'),
                    },
                }

            prompt_trace = _collect_prompt_trace(optimizer) or {}
            bundle_site_context = _as_dict(bundle.get('site_context'))
            bundle_content_policy = _as_dict(bundle.get('content_policy'))
            bundle_prompt_profile = _as_dict(bundle.get('prompt_profile'))
            trace_resolved = _as_dict(prompt_trace.get('resolved'))

            return {
                'status': 'ok',
                'mode': mode,
                'prompt': prompt_trace.get('prompt') or '',
                'preview_text': preview,
                'preview_json': preview_json,
                'model': _collect_prompt_model_info(optimizer),
                'prompt_source': prompt_trace.get('prompt_source'),
                'template_version': prompt_trace.get('template_version'),
                'rendered_variables': prompt_trace.get('rendered_variables'),
                'resolved': {
                    'site_code': bundle_site_context.get('site_code'),
                    'listing_language': trace_resolved.get('listing_language') or bundle_site_context.get('listing_language'),
                    'content_policy_code': bundle_content_policy.get('content_policy_code'),
                    'prompt_profile_code': bundle_prompt_profile.get('prompt_profile_code'),
                },
            }
        finally:
            optimizer.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Prompt preview failed: {exc}') from exc


@app.post('/ops-configs/profit-trial')
def profit_trial_endpoint(payload: ProfitTrialPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    try:
        module = _load_profit_analyzer_module()
        analyzer = module.ProfitAnalyzer(target_profit_rate=payload.target_profit_rate)
        bundle = analyzer._resolve_runtime_bundle({
            'market_code': payload.market_code,
            'site_code': payload.site_code,
        })
        bundle = _apply_bundle_overrides(
            bundle,
            shipping_profile_code=payload.shipping_profile_code,
            fee_profile_code=payload.fee_profile_code,
        )

        if payload.product_id_new:
            product = _resolve_debug_product_or_404(payload.product_id_new)
            rows = analyzer.fetch_target_rows([str(product.get('alibaba_product_id') or '')])
            entries = analyzer.dedupe_rows(rows, site_context=bundle.get('site_context'))
            results = [
                analyzer.analyze_row(entry, bundle=bundle)
                for entry in entries
                if str(entry.get('product_id_new') or '') == str(product.get('product_id_new') or '')
            ]
            return {
                'status': 'ok',
                'results': results,
                'product_summary': {
                    'product_id_new': product.get('product_id_new'),
                    'alibaba_product_id': product.get('alibaba_product_id'),
                    'title': product.get('optimized_title') or product.get('title'),
                    'sku_count': len(results),
                },
                'resolved': {
                    'site_code': _as_dict(bundle.get('site_context')).get('site_code'),
                    'shipping_profile_code': _as_dict(bundle.get('shipping_profile')).get('shipping_profile_code'),
                    'fee_profile_code': _as_dict(bundle.get('fee_profile')).get('fee_profile_code'),
                    'product_id_new': product.get('product_id_new'),
                },
            }

        if payload.title is None or payload.sku_name is None or payload.price_cny is None or payload.package_weight is None:
            raise HTTPException(status_code=422, detail='title, sku_name, price_cny and package_weight are required when product_id_new is not provided')

        result = analyzer.analyze_row({
            'title': payload.title,
            'sku_name': payload.sku_name,
            'price': payload.price_cny,
            'package_weight': payload.package_weight,
            'package_length': payload.package_length,
            'package_width': payload.package_width,
            'package_height': payload.package_height,
            'product_id_new': 'PREVIEW',
            'product_id': 'PREVIEW',
            'alibaba_product_id': 'PREVIEW',
            'status': 'preview',
            'unique_key': f'preview|{payload.site_code or payload.market_code or "default"}|{payload.sku_name}',
            'created_at': datetime.now().isoformat(),
            'listing_updated_at': datetime.now().isoformat(),
            'logistics': {},
            'product_skus': [],
        }, bundle=bundle)
        return {
            'status': 'ok',
            'result': result,
            'resolved': {
                'site_code': _as_dict(bundle.get('site_context')).get('site_code'),
                'shipping_profile_code': _as_dict(bundle.get('shipping_profile')).get('shipping_profile_code'),
                'fee_profile_code': _as_dict(bundle.get('fee_profile')).get('fee_profile_code'),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Profit trial failed: {exc}') from exc


@app.get('/ops-configs/site-listings')
def list_site_listings_endpoint(
    request: Request,
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    publish_status: str | None = None,
    sync_status: str | None = None,
):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    return fetch_site_listings(
        page=page,
        page_size=page_size,
        keyword=keyword,
        site_code=site_code,
        publish_status=publish_status,
        sync_status=sync_status,
    )


@app.get('/ops-configs/site-listings/{site_listing_id}')
def get_site_listing_endpoint(site_listing_id: int, request: Request):
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    listing = fetch_site_listing(site_listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail='Site listing not found')
    return listing


@app.get('/system-configs')
def list_system_configs(
    page: int = 1,
    page_size: int = 100,
    category: str | None = None,
    environment: str | None = None,
    keyword: str | None = None,
    verify_status: str | None = None,
    is_active: bool | None = None,
):
    return fetch_system_configs(
        page=page,
        page_size=page_size,
        category=category,
        environment=environment,
        keyword=keyword,
        verify_status=verify_status,
        is_active=is_active,
    )


@app.get('/system-configs/{config_key}')
def get_system_config(config_key: str, environment: str = 'prod'):
    config_item = fetch_system_config(config_key, environment=environment)
    if not config_item:
        raise HTTPException(status_code=404, detail='Config not found')
    return config_item


@app.put('/system-configs/{config_key}')
def put_system_config(config_key: str, payload: SystemConfigUpdatePayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    config_item = fetch_system_config(config_key, environment=payload.environment)
    if not config_item:
        raise HTTPException(status_code=404, detail='Config not found')
    _require_any_role(user, _allowed_config_roles(str(config_item.get('secret_level'))))
    _validate_config_payload(payload, config_item)
    updated = upsert_system_config_record(config_key, {
        **payload.model_dump(exclude_none=True),
        'operator_name': user['display_name'],
    })
    if not updated:
        raise HTTPException(status_code=404, detail='Config not found')
    return {'status': 'ok', 'config': updated, 'message': '配置已保存'}


@app.post('/system-configs/{config_key}/rollback/{log_id}')
def rollback_system_config(config_key: str, log_id: int, request: Request, environment: str = 'prod') -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    config_item = fetch_system_config(config_key, environment=environment)
    if not config_item:
        raise HTTPException(status_code=404, detail='Config not found')
    _require_any_role(user, _allowed_config_roles(str(config_item.get('secret_level'))))
    updated = rollback_system_config_record(config_key, environment, log_id, user['display_name'])
    if not updated:
        raise HTTPException(status_code=404, detail='Rollback target not found')
    return {'status': 'ok', 'config': updated, 'message': '配置已回滚'}


@app.post('/media-assets/uploads')
def create_media_upload(payload: MediaUploadRequestPayload, request: Request) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    product = fetch_product(payload.product_id)
    _validate_media_request(payload, product)
    return {'status': 'ok', 'ticket': create_media_upload_ticket(payload.model_dump())}


@app.put('/media-assets/uploads/{upload_token}')
async def upload_media_file(upload_token: str, request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_any_role(user, {'operator', 'admin', 'owner'})
    file_bytes = await file.read()
    try:
        asset = store_media_asset(upload_token, file_bytes, user['display_name'])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {'status': 'ok', 'asset': asset, 'message': '媒体已上传'}


@app.get('/media-assets/{asset_id}/content')
def get_media_asset_content(asset_id: int):
    try:
        url = get_media_asset_download_url(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=404, detail='Media asset not found')
    return RedirectResponse(url)


@app.get('/tasks/{task_name}')
def get_task(task_name: str):
    task = fetch_task(task_name)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    return task


@app.get('/tasks/{task_name}/logs')
def get_logs_for_task(task_name: str, limit: int = 200):
    return {'items': fetch_task_logs(task_name, limit=limit)}