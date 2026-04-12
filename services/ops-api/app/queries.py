"""Read queries for the ops dashboard API."""
from __future__ import annotations

import base64
import io
from copy import deepcopy
from collections.abc import Mapping
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
import runpy
from urllib.parse import urlparse
import uuid
from typing import Any, Dict, List, Tuple, cast

import boto3  # type: ignore[import-untyped]
from botocore.config import Config as BotoConfig  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from cryptography.fernet import Fernet, InvalidToken
from PIL import Image, UnidentifiedImageError
from psycopg2.extras import Json

from .config import settings
from .db import get_connection

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ENV_PATH = WORKSPACE_ROOT / 'config' / 'config.env'
LLM_CONFIG_PATH = WORKSPACE_ROOT / 'config' / 'llm_config.py'
TITLE_PROMPT_PATH = WORKSPACE_ROOT / 'config' / 'prompts' / 'title_prompt_v3.md'
DESC_PROMPT_PATH = WORKSPACE_ROOT / 'config' / 'prompts' / 'desc_prompt_v3.md'
SKU_PROMPT_PATH = WORKSPACE_ROOT / 'config' / 'prompts' / 'sku_name_prompt_v1.md'
MEDIA_UPLOAD_ROOT = WORKSPACE_ROOT / settings.media_upload_dir
_foundation_tables_ready = False
_prompt_template_defaults: Dict[str, str] | None = None
GLOBAL_PROMPT_PROFILE_CODE = 'prompt_global_shopee'
GLOBAL_PROMPT_PROFILE_SITE_CODE = 'global'

DEFAULT_SKU_NAME_TEMPLATE = """# Shopee 全站点 SKU 规格命名提示词 v1.0

## 运行上下文
- 站点：{site_code}
- 语言：{listing_language}
- 商品标题：{product_title}
- 商品描述：{product_description}
- 原始SKU名称：{original_sku_name}
- 尺寸提示：{dimension_hint}
- 最大长度：{max_length}

## 任务目标
输出一个适合买家阅读的SKU名称。

---

## 语言硬约束

根据 `{listing_language}` 参数输出对应语言的SKU名称：

| listing_language | 输出要求 |
|-----------------|---------|
| zh-Hant | 台湾繁体中文 |
| en | 英文 |
| id | 印尼语 |
| th | 泰语 |
| vi | 越南语 |
| ms | 马来语 |
| pt | 巴西葡萄牙语 |
| es | 墨西哥西班牙语 |

---

## SKU命名原则

### 信息优先级
```
颜色 > 尺寸 > 型号 > 材质 > 其他差异
```

### 信息提取来源
1. 优先从 `{original_sku_name}` 提取关键差异信息
2. 其次从 `{dimension_hint}` 获取尺寸信息
3. 最后从 `{product_title}` 和 `{product_description}` 补充

### 命名规范
✅ 保留关键差异信息（颜色/尺寸/型号）
✅ 自然、简洁、买家易理解
✅ 长度不超过 {max_length} 个字符
✅ 如有多个差异，用空格或 `-` 分隔

❌ 不要重复整条商品标题
❌ 不要包含营销词汇
❌ 不要过于技术化或内部编码

---

## 命名格式建议

### 单一差异
```
颜色：White / 白色 / Putih
尺寸：30cm / 30x20cm / Medium
型号：Model A / Type 1
```

### 多重差异
```
颜色+尺寸：White 30cm / 白色 30cm
颜色+型号：Black Model A / 黑色 A款
尺寸+材质：Large Cotton / 大号 棉质
```

### 站点本地化示例

| 站点 | SKU命名示例 |
|-----|------------|
| 台湾 | 白色 30cm / 黑色 L號 / 灰色 3層 |
| 菲律宾 | White 30cm / Black Large / Grey 3-Tier |
| 印尼 | Putih 30cm / Hitam Besar / Abu 3-Lapis |
| 泰国 | สีขาว 30cm / สีดำ ไซส์ใหญ่ |
| 越南 | Trắng 30cm / Đen Cỡ lớn |
| 巴西 | Branco 30cm / Preto Grande |

---

## 长度控制

**最大长度：** {max_length} 个字符

**建议长度：**
- 中文站点：10-25字符
- 英文站点：10-30字符
- 其他语言：15-35字符

**过长处理：**
- 优先保留最重要的差异信息
- 省略次要信息
- 使用缩写（如 L/XL/XXL, S/M/L）

---

## 跨境合规禁止事项

### 绝对禁止（所有站点）
```
❌ 本地库存暗示：
   现货/現貨/Ready Stock
   
❌ 营销词汇：
   热销/爆款/Best Seller/限量/Limited
   
❌ 物流优惠：
   包邮/免运/Free Shipping
```

---

## 输出要求

**只输出一个SKU名称。**

❌ 不要输出解释
❌ 不要输出多个候选
❌ 不要输出引号或项目符号

**输出格式：** 直接输出SKU名称文本，无任何额外内容。
"""

SUPPORTED_PROMPT_SITE_LANGUAGES: Dict[str, Dict[str, Any]] = {
    'shopee_tw': {'language': 'zh-Hant', 'site_name': '台湾'},
    'shopee_ph': {'language': 'en', 'site_name': '菲律宾'},
    'shopee_id': {'language': 'id', 'site_name': '印度尼西亚'},
    'shopee_th': {'language': 'th', 'site_name': '泰国'},
    'shopee_vn': {'language': 'vi', 'site_name': '越南'},
    'shopee_my': {'language': 'en/ms', 'site_name': '马来西亚'},
    'shopee_sg': {'language': 'en', 'site_name': '新加坡'},
    'shopee_br': {'language': 'pt', 'site_name': '巴西'},
    'shopee_mx': {'language': 'es', 'site_name': '墨西哥'},
}

DEFAULT_PROMPT_TEMPLATE_VARIABLES: Dict[str, Any] = {
    'title': {
        'site_code': {'required': True, 'default': '', 'label': '站点代码'},
        'listing_language': {'required': True, 'default': '', 'label': '上架语言'},
        'original_title': {'required': True, 'default': '', 'label': '1688原始标题'},
        'attributes': {'required': True, 'default': '', 'label': '商品属性'},
        'hot_search_words': {'required': True, 'default': '', 'label': '热搜关键词'},
    },
    'description': {
        'site_code': {'required': True, 'default': '', 'label': '站点代码'},
        'listing_language': {'required': True, 'default': '', 'label': '上架语言'},
        'product_name': {'required': True, 'default': '', 'label': '商品名称'},
        'material': {'required': True, 'default': '', 'label': '材质'},
        'features': {'required': True, 'default': '', 'label': '核心特点'},
        'scenarios': {'required': True, 'default': '', 'label': '适用场景'},
        'hot_search_words': {'required': True, 'default': '', 'label': '热搜关键词'},
    },
    'sku': {
        'site_code': {'required': True, 'default': '', 'label': '站点代码'},
        'listing_language': {'required': True, 'default': '', 'label': '上架语言'},
        'product_title': {'required': True, 'default': '', 'label': '商品标题'},
        'product_description': {'required': True, 'default': '', 'label': '商品描述'},
        'original_sku_name': {'required': True, 'default': '', 'label': '原始SKU名称'},
        'dimension_hint': {'required': False, 'default': '', 'label': '尺寸提示'},
        'max_length': {'required': False, 'default': '30', 'label': '最大长度'},
    },
}

SERVICE_CATALOG: List[Dict[str, Any]] = [
    {
        'id': 3,
        'code': 'e-commerce',
        'name': 'E-commerce',
        'type': 'service',
        'status': 'active',
        'owner': 'openclaw',
        'description': 'OpenClaw 电商自动化服务，承载当前工作区的任务、日志和心跳。',
        'source_system': 'openclaw',
        'metadata': {'workspace': 'workspace-e-commerce'},
    },
    {
        'id': 1,
        'code': 'main',
        'name': 'Main',
        'type': 'service',
        'status': 'active',
        'owner': 'openclaw',
        'description': 'OpenClaw 主运行时服务。当前工作区尚未接入该服务数据。',
        'source_system': 'openclaw',
        'metadata': {'workspace': 'global'},
    },
    {
        'id': 2,
        'code': 'dev',
        'name': 'Dev',
        'type': 'service',
        'status': 'active',
        'owner': 'openclaw',
        'description': 'OpenClaw 开发与调试服务。当前工作区尚未接入该服务数据。',
        'source_system': 'openclaw',
        'metadata': {'workspace': 'global'},
    },
]

ECOMMERCE_SERVICE_ID = 3


def _fetch_task_lifecycle_metrics(cur: Any) -> Dict[str, Any]:
    cur.execute(
        """
        SELECT metric_name, metric_value, calculated_at
        FROM dashboard_metrics
        WHERE metric_scope = 'task-lifecycle'
          AND metric_window = 'current'
          AND agent_id IS NULL
        ORDER BY metric_name ASC
        """
    )
    stage_distribution: Dict[str, int] = {}
    stage_status_distribution: Dict[str, int] = {}
    metric_timestamp = None

    for raw_row in cur.fetchall():
        row = cast(Dict[str, Any], raw_row)
        metric_name = str(row.get('metric_name') or '')
        metric_value = int(float(row.get('metric_value') or 0))
        calculated_at = cast(datetime | None, row.get('calculated_at'))
        if calculated_at and (metric_timestamp is None or calculated_at > metric_timestamp):
            metric_timestamp = calculated_at

        if metric_name.startswith('tasks.stage.'):
            stage_distribution[metric_name.split('tasks.stage.', 1)[1]] = metric_value
        elif metric_name.startswith('tasks.stage_status.'):
            stage_status_distribution[metric_name.split('tasks.stage_status.', 1)[1]] = metric_value

    return {
        'stage_distribution': stage_distribution,
        'stage_status_distribution': stage_status_distribution,
        'metric_timestamp': metric_timestamp.isoformat() if metric_timestamp else None,
    }


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('utf-8').rstrip('=')


def _base64url_decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _serialize_media_payload(payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(settings.media_upload_secret.encode('utf-8'), payload_json, hashlib.sha256).hexdigest()
    return f"{_base64url_encode(payload_json)}.{signature}"


def _deserialize_media_payload(token: str) -> Dict[str, Any]:
    encoded_payload, signature = token.split('.', 1)
    payload_bytes = _base64url_decode(encoded_payload)
    expected = hmac.new(settings.media_upload_secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError('invalid upload token')
    payload = cast(Dict[str, Any], json.loads(payload_bytes.decode('utf-8')))
    if int(payload.get('expires_at_ts', 0)) < int(datetime.now().timestamp()):
        raise ValueError('upload token expired')
    return payload


def _build_fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.config_encryption_secret.encode('utf-8')).digest())
    return Fernet(key)


def _encrypt_config_value(value: str | None) -> str | None:
    if value is None:
        return None
    return _build_fernet().encrypt(value.encode('utf-8')).decode('utf-8')


def _decrypt_config_value(value_encrypted: str | None) -> str | None:
    if not value_encrypted:
        return None
    try:
        return _build_fernet().decrypt(value_encrypted.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise ValueError('invalid encrypted config value') from exc


def _build_s3_client() -> Any:
    if not settings.s3_bucket:
        raise ValueError('S3 bucket is not configured')
    if not settings.s3_access_key_id or not settings.s3_secret_access_key:
        raise ValueError('S3 credentials are not configured')

    endpoint_url = settings.s3_endpoint_url.strip()
    addressing_style = settings.s3_addressing_style.strip().lower() or 'auto'
    if addressing_style == 'auto' and 'myqcloud.com' in endpoint_url.lower():
        addressing_style = 'virtual'

    config_kwargs: Dict[str, Any] = {
        'signature_version': 's3v4',
    }
    if addressing_style in {'virtual', 'path'}:
        config_kwargs['s3'] = {'addressing_style': addressing_style}

    client_kwargs: Dict[str, Any] = {
        'service_name': 's3',
        'region_name': settings.s3_region,
        'aws_access_key_id': settings.s3_access_key_id,
        'aws_secret_access_key': settings.s3_secret_access_key,
        'config': BotoConfig(**config_kwargs),
    }
    if endpoint_url:
        client_kwargs['endpoint_url'] = endpoint_url
    boto3_module: Any = boto3
    s3_client: Any = boto3_module.client(**client_kwargs)
    return s3_client


def _build_s3_object_key(product_id: int, usage_type: str, file_name: str) -> str:
    safe_name = Path(file_name).name.replace(' ', '_')
    date_prefix = datetime.now().strftime('%Y/%m/%d')
    return f"{settings.s3_prefix.strip('/')}/{product_id}/{usage_type}/{date_prefix}/{uuid.uuid4().hex}-{safe_name}"


def _build_s3_asset_url(object_key: str) -> str:
    base = settings.s3_public_base_url.strip()
    if base:
        return f"{base.rstrip('/')}/{object_key}"
    return ''


def _validate_and_probe_image(file_bytes: bytes) -> Dict[str, Any]:
    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            image.load()
            width, height = image.size
            mime_type = Image.MIME.get(image.format or '', 'application/octet-stream')
    except UnidentifiedImageError as exc:
        raise ValueError('invalid image file') from exc

    if width > settings.media_max_image_width or height > settings.media_max_image_height:
        raise ValueError(f'image dimensions exceed limit {settings.media_max_image_width}x{settings.media_max_image_height}')

    return {
        'width_px': width,
        'height_px': height,
        'mime_type': mime_type,
    }


def _media_content_path(asset_id: int) -> str:
    return f'/media-assets/{asset_id}/content'


def _serialize_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat(timespec='seconds')
    return None


def _build_product_cos_dir_name(product_id_new: str, title: str | None) -> str:
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title or '')
    title_bytes = safe_title.encode('utf-8')
    if len(title_bytes) > 50:
        safe_title = title_bytes[:50].decode('utf-8', errors='ignore')
    return f"{product_id_new}_{safe_title}" if safe_title else product_id_new


def _get_product_cos_title(product: Dict[str, Any]) -> str | None:
    original_title = str(product.get('original_title') or '').strip()
    if original_title:
        return original_title
    title = str(product.get('title') or '').strip()
    return title or None


def _generate_s3_object_download_url(object_key: str) -> str:
    return cast(str, _build_s3_client().generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.s3_bucket, 'Key': object_key},
        ExpiresIn=900,
    ))


def _resolve_scraped_image_urls_via_cos(product: Dict[str, Any], image_type: str, fallback_urls: List[Any]) -> List[Any]:
    product_id_new = str(product.get('product_id_new') or '').strip()
    if not product_id_new:
        return fallback_urls

    subdir_map = {
        'main_images': 'main_images/',
        'sku_images': 'sku_images/',
        'detail_images': 'detail_images/',
    }
    subdir = subdir_map.get(image_type)
    if not subdir:
        return fallback_urls

    prefix = f"{_build_product_cos_dir_name(product_id_new, _get_product_cos_title(product))}{('/' + subdir) if not subdir.startswith('/') else subdir}"
    prefix = prefix.lstrip('/')

    try:
        response = _build_s3_client().list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix, MaxKeys=200)
        contents = cast(List[Dict[str, Any]], response.get('Contents') or [])
        if not contents:
            return fallback_urls
        keys = sorted(
            [str(item.get('Key') or '') for item in contents if str(item.get('Key') or '').startswith(prefix)],
        )
        if not keys:
            return fallback_urls
        return [_generate_s3_object_download_url(key) for key in keys]
    except (BotoCoreError, ClientError, ValueError):
        return fallback_urls


def _resolve_product_preview_image_url(product: Dict[str, Any]) -> str | None:
    raw_images = cast(List[Any], product.get('main_images') or [])
    if not raw_images:
        return None
    resolved = _resolve_scraped_image_urls_via_cos(product, 'main_images', raw_images)
    first = resolved[0] if resolved else None
    return str(first) if isinstance(first, str) and first else None


def _extract_row_value(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        mapping_row = cast(Mapping[str, Any], row)
        return mapping_row.get(key)
    if isinstance(row, (list, tuple)) and row:
        return cast(Any, row[0])
    return None


def _read_prompt_template(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def _get_prompt_template_defaults() -> Dict[str, str]:
    global _prompt_template_defaults
    if _prompt_template_defaults is None:
        _prompt_template_defaults = {
            'title_template': _read_prompt_template(TITLE_PROMPT_PATH),
            'description_template': _read_prompt_template(DESC_PROMPT_PATH),
            'sku_name_template': _read_prompt_template(SKU_PROMPT_PATH) or DEFAULT_SKU_NAME_TEMPLATE.strip(),
        }
    return _prompt_template_defaults


def _build_global_prompt_profile_metadata() -> Dict[str, Any]:
    return {
        'template_version': 'multisite-v1.0',
        'seed_source': 'global_prompt_baseline',
        'is_global_template': True,
        'supported_sites': list(SUPPORTED_PROMPT_SITE_LANGUAGES.keys()),
        'supported_languages': sorted({str(item.get('language') or 'zh-Hant') for item in SUPPORTED_PROMPT_SITE_LANGUAGES.values()}),
        'site_name': 'Shopee Global',
    }


def _build_global_prompt_profile_variable_schema() -> Dict[str, Any]:
    return deepcopy(DEFAULT_PROMPT_TEMPLATE_VARIABLES)


def _ensure_foundation_tables() -> None:
    global _foundation_tables_ready
    if _foundation_tables_ready:
        return

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.media_assets (
                id BIGSERIAL PRIMARY KEY,
                owner_type VARCHAR(32) NOT NULL,
                owner_id BIGINT NOT NULL,
                site_scope VARCHAR(20),
                shop_code VARCHAR(64),
                media_type VARCHAR(20) NOT NULL,
                usage_type VARCHAR(30) NOT NULL,
                source_url TEXT,
                oss_key TEXT,
                oss_url TEXT,
                file_name VARCHAR(255),
                mime_type VARCHAR(128),
                file_size_bytes BIGINT,
                width_px INTEGER,
                height_px INTEGER,
                duration_seconds NUMERIC(10, 2),
                sort_order INTEGER DEFAULT 0,
                status VARCHAR(30) DEFAULT 'active',
                checksum VARCHAR(128),
                uploaded_by VARCHAR(128),
                uploaded_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted SMALLINT DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_media_assets_owner ON public.media_assets(owner_type, owner_id);
            CREATE INDEX IF NOT EXISTS idx_media_assets_scope ON public.media_assets(site_scope, usage_type);

            CREATE TABLE IF NOT EXISTS public.system_configs (
                id BIGSERIAL PRIMARY KEY,
                config_key VARCHAR(128) NOT NULL,
                config_name VARCHAR(128) NOT NULL,
                category VARCHAR(64) NOT NULL,
                environment VARCHAR(32) NOT NULL DEFAULT 'prod',
                value_type VARCHAR(32) NOT NULL,
                secret_level VARCHAR(32) NOT NULL DEFAULT 'masked',
                value_encrypted TEXT,
                value_masked TEXT,
                file_ref_id BIGINT,
                description TEXT,
                schema_json JSONB DEFAULT '{}'::jsonb,
                dependency_json JSONB DEFAULT '{}'::jsonb,
                is_required BOOLEAN DEFAULT TRUE,
                is_active BOOLEAN DEFAULT TRUE,
                rotation_days INTEGER,
                expires_at TIMESTAMP,
                last_verified_at TIMESTAMP,
                last_verify_status VARCHAR(32) DEFAULT 'unknown',
                last_verify_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR(128),
                CONSTRAINT system_configs_unique_key UNIQUE (config_key, environment)
            );

            CREATE INDEX IF NOT EXISTS idx_system_configs_category ON public.system_configs(category, environment);
            CREATE INDEX IF NOT EXISTS idx_system_configs_verify_status ON public.system_configs(last_verify_status, is_active);

            CREATE TABLE IF NOT EXISTS public.config_change_logs (
                id BIGSERIAL PRIMARY KEY,
                config_id BIGINT NOT NULL REFERENCES public.system_configs(id),
                action_type VARCHAR(32) NOT NULL,
                old_value_encrypted TEXT,
                old_value_masked TEXT,
                new_value_encrypted TEXT,
                new_value_masked TEXT,
                change_reason TEXT,
                verify_status VARCHAR(32),
                verify_message TEXT,
                operator_id VARCHAR(64),
                operator_name VARCHAR(128),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_config_change_logs_config_id ON public.config_change_logs(config_id, created_at DESC);

            ALTER TABLE public.config_change_logs ADD COLUMN IF NOT EXISTS old_value_encrypted TEXT;
            ALTER TABLE public.config_change_logs ADD COLUMN IF NOT EXISTS new_value_encrypted TEXT;

            CREATE TABLE IF NOT EXISTS public.prompt_profiles (
                id BIGSERIAL PRIMARY KEY,
                prompt_profile_code VARCHAR(64) NOT NULL,
                profile_name VARCHAR(128),
                market_code VARCHAR(64),
                site_code VARCHAR(64) NOT NULL,
                title_template TEXT,
                description_template TEXT,
                sku_name_template TEXT,
                template_variables_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                notes TEXT,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_prompt_profiles_code UNIQUE (prompt_profile_code)
            );

            CREATE INDEX IF NOT EXISTS idx_prompt_profiles_site_default
                ON public.prompt_profiles(site_code, is_default, is_active);

            CREATE TABLE IF NOT EXISTS public.fee_profiles (
                id BIGSERIAL PRIMARY KEY,
                fee_profile_code VARCHAR(64) NOT NULL,
                profile_name VARCHAR(128),
                market_code VARCHAR(64),
                site_code VARCHAR(64) NOT NULL,
                currency VARCHAR(10) NOT NULL DEFAULT 'TWD',
                commission_rate NUMERIC(10, 4),
                transaction_fee_rate NUMERIC(10, 4),
                pre_sale_service_rate NUMERIC(10, 4),
                tax_rate NUMERIC(10, 4),
                agent_fee_cny NUMERIC(10, 2),
                commission_free_days INTEGER,
                buyer_shipping_ordinary NUMERIC(10, 2),
                buyer_shipping_discount NUMERIC(10, 2),
                buyer_shipping_free NUMERIC(10, 2),
                hidden_price_mode VARCHAR(64),
                hidden_price_value NUMERIC(10, 4),
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_fee_profiles_code UNIQUE (fee_profile_code)
            );

            CREATE INDEX IF NOT EXISTS idx_fee_profiles_site_default
                ON public.fee_profiles(site_code, is_default, is_active);

            ALTER TABLE public.content_policies ADD COLUMN IF NOT EXISTS prompt_profile_code VARCHAR(64);
            ALTER TABLE public.market_configs ADD COLUMN IF NOT EXISTS commission_free_days INTEGER;

            UPDATE public.content_policies
            SET prompt_profile_code = CONCAT('prompt_', content_policy_code)
            WHERE COALESCE(prompt_profile_code, '') = '';

            UPDATE public.market_configs
            SET commission_free_days = COALESCE(commission_free_days, 90)
            WHERE commission_free_days IS NULL;

            INSERT INTO public.prompt_profiles (
                prompt_profile_code,
                profile_name,
                market_code,
                site_code,
                title_template,
                description_template,
                is_default,
                is_active,
                metadata
            )
            SELECT
                CONCAT('prompt_', cp.content_policy_code),
                COALESCE(cp.policy_name, cp.content_policy_code),
                cp.market_code,
                cp.site_code,
                COALESCE(NULLIF(cp.prompt_title_variant, ''), NULLIF(cp.prompt_base_template, '')),
                COALESCE(NULLIF(cp.prompt_desc_variant, ''), NULLIF(cp.prompt_base_template, '')),
                cp.is_default,
                cp.is_active,
                jsonb_build_object('seeded_from_content_policy_code', cp.content_policy_code)
            FROM public.content_policies cp
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.prompt_profiles pp
                WHERE pp.prompt_profile_code = CONCAT('prompt_', cp.content_policy_code)
            );

            INSERT INTO public.fee_profiles (
                fee_profile_code,
                profile_name,
                market_code,
                site_code,
                currency,
                commission_rate,
                transaction_fee_rate,
                pre_sale_service_rate,
                agent_fee_cny,
                commission_free_days,
                buyer_shipping_ordinary,
                buyer_shipping_discount,
                buyer_shipping_free,
                is_default,
                is_active,
                metadata
            )
            SELECT
                CONCAT('fee_', mc.market_code),
                COALESCE(mc.config_name, mc.market_code),
                mc.market_code,
                mc.site_code,
                mc.default_currency,
                NULLIF(sp.metadata ->> 'commission_rate', '')::numeric,
                NULLIF(sp.metadata ->> 'transaction_fee_rate', '')::numeric,
                NULLIF(sp.metadata ->> 'pre_sale_service_rate', '')::numeric,
                NULLIF(sp.metadata ->> 'agent_fee_cny', '')::numeric,
                COALESCE(mc.commission_free_days, NULLIF(sp.metadata ->> 'commission_free_days', '')::integer, 90),
                NULLIF(sp.subsidy_rules_json ->> 'ordinary_buyer_shipping', '')::numeric,
                NULLIF(sp.subsidy_rules_json ->> 'discount_buyer_shipping', '')::numeric,
                NULLIF(sp.subsidy_rules_json ->> 'free_buyer_shipping', '')::numeric,
                TRUE,
                mc.is_active,
                jsonb_build_object('seeded_from_market_code', mc.market_code, 'seeded_from_shipping_profile_code', sp.shipping_profile_code)
            FROM public.market_configs mc
            LEFT JOIN public.shipping_profiles sp
              ON sp.shipping_profile_code = mc.default_shipping_profile_code
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.fee_profiles fp
                WHERE fp.fee_profile_code = CONCAT('fee_', mc.market_code)
            );
            """
        )
        prompt_defaults = _get_prompt_template_defaults()
        cur.execute(
            """
            UPDATE public.prompt_profiles
            SET title_template = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE COALESCE(title_template, '') = ''
            """,
            (prompt_defaults['title_template'],),
        )
        cur.execute(
            """
            UPDATE public.prompt_profiles
            SET description_template = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE COALESCE(description_template, '') = ''
            """,
            (prompt_defaults['description_template'],),
        )
        cur.execute(
            """
            UPDATE public.prompt_profiles
            SET sku_name_template = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE COALESCE(sku_name_template, '') = ''
            """,
            (prompt_defaults['sku_name_template'],),
        )
        cur.execute(
            """
            INSERT INTO public.prompt_profiles (
                prompt_profile_code,
                profile_name,
                market_code,
                site_code,
                title_template,
                description_template,
                sku_name_template,
                template_variables_json,
                notes,
                is_default,
                is_active,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, TRUE, TRUE, %s::jsonb)
            ON CONFLICT (prompt_profile_code) DO UPDATE
            SET profile_name = EXCLUDED.profile_name,
                market_code = EXCLUDED.market_code,
                site_code = EXCLUDED.site_code,
                title_template = EXCLUDED.title_template,
                description_template = EXCLUDED.description_template,
                sku_name_template = EXCLUDED.sku_name_template,
                template_variables_json = EXCLUDED.template_variables_json,
                notes = EXCLUDED.notes,
                is_default = EXCLUDED.is_default,
                is_active = EXCLUDED.is_active,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            WHERE COALESCE(public.prompt_profiles.metadata ->> 'seed_source', '') IN ('global_prompt_baseline', 'multisite_prompt_baseline')
               OR COALESCE(public.prompt_profiles.metadata ->> 'is_global_template', 'false') = 'true'
               OR COALESCE(public.prompt_profiles.metadata ->> 'is_multisite_baseline', 'false') = 'true'
            """,
            (
                GLOBAL_PROMPT_PROFILE_CODE,
                'Shopee 全站点全局模板',
                'shopee_global',
                GLOBAL_PROMPT_PROFILE_SITE_CODE,
                prompt_defaults['title_template'],
                prompt_defaults['description_template'],
                prompt_defaults['sku_name_template'],
                json.dumps(_build_global_prompt_profile_variable_schema(), ensure_ascii=False),
                '系统生成的全局提示词模板，供所有 Shopee 站点共享。',
                json.dumps(_build_global_prompt_profile_metadata(), ensure_ascii=False),
            ),
        )
        cur.execute(
            """
            UPDATE public.content_policies cp
            SET prompt_profile_code = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE EXISTS (
                SELECT 1
                FROM public.prompt_profiles pp
                WHERE pp.prompt_profile_code = %s
            )
              AND (
                COALESCE(cp.prompt_profile_code, '') = ''
                OR cp.prompt_profile_code = CONCAT('prompt_', cp.content_policy_code)
                                OR cp.prompt_profile_code LIKE 'prompt_baseline_shopee_%%'
              )
            """,
            (GLOBAL_PROMPT_PROFILE_CODE, GLOBAL_PROMPT_PROFILE_CODE),
        )
        cur.execute(
            """
            UPDATE public.prompt_profiles pp
            SET is_active = FALSE,
                metadata = COALESCE(pp.metadata, '{}'::jsonb) || jsonb_build_object(
                    'legacy_template', true,
                    'replaced_by', %s
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE pp.prompt_profile_code <> %s
              AND EXISTS (
                SELECT 1
                FROM public.prompt_profiles replacement
                WHERE replacement.prompt_profile_code = %s
              )
              AND (
                COALESCE(pp.metadata ->> 'seeded_from_content_policy_code', '') <> ''
                OR COALESCE(pp.metadata ->> 'seed_source', '') = 'multisite_prompt_baseline'
                OR COALESCE(pp.metadata ->> 'is_multisite_baseline', 'false') = 'true'
              )
            """,
            (GLOBAL_PROMPT_PROFILE_CODE, GLOBAL_PROMPT_PROFILE_CODE, GLOBAL_PROMPT_PROFILE_CODE),
        )
        cur.execute(
            """
            UPDATE public.fee_profiles fp
            SET commission_rate = COALESCE(fp.commission_rate, 0.14),
                transaction_fee_rate = COALESCE(fp.transaction_fee_rate, 0.025),
                pre_sale_service_rate = COALESCE(fp.pre_sale_service_rate, 0.0),
                agent_fee_cny = COALESCE(fp.agent_fee_cny, 3.0),
                commission_free_days = COALESCE(fp.commission_free_days, mc.commission_free_days, 90),
                updated_at = CURRENT_TIMESTAMP
            FROM public.market_configs mc
            WHERE mc.site_code = fp.site_code
              AND (
                fp.commission_rate IS NULL
                OR fp.transaction_fee_rate IS NULL
                OR fp.pre_sale_service_rate IS NULL
                OR fp.agent_fee_cny IS NULL
                OR fp.commission_free_days IS NULL
              )
            """
        )
        conn.commit()

    _foundation_tables_ready = True


def _normalize_site_code_value(site: str | None) -> str | None:
    raw = (site or '').strip()
    if not raw:
        return None
    lowered = raw.lower()
    if '_' in lowered:
        return lowered
    return f'shopee_{lowered}'


def _to_legacy_site_label(site: Any) -> str | None:
    raw = '' if site is None else str(site).strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered.startswith('shopee_'):
        return lowered.split('_', 1)[1].upper()
    return raw.upper()


def _as_string_dict(value: Any) -> Dict[str, Any]:
    return cast(Dict[str, Any], value) if isinstance(value, dict) else {}


def _legacy_site_label_expr(expr: str) -> str:
    return f"UPPER(CASE WHEN LOWER({expr}) LIKE 'shopee_%%' THEN REPLACE(LOWER({expr}), 'shopee_', '') ELSE {expr} END)"


def _profit_analysis_site_code_expr(alias: str = 'pa') -> str:
    raw_expr = f"COALESCE(NULLIF({alias}.site, ''), 'shopee_tw')"
    return f"CASE WHEN POSITION('_' IN LOWER({raw_expr})) > 0 THEN LOWER({raw_expr}) ELSE CONCAT('shopee_', LOWER({raw_expr})) END"


def _profit_analysis_site_expr(alias: str = 'pa') -> str:
    return _legacy_site_label_expr(_profit_analysis_site_code_expr(alias))


def _profit_analysis_market_code_expr(alias: str = 'pa') -> str:
    return _profit_analysis_site_code_expr(alias)


def _isoformat_timestamp(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds')


def _load_config_env() -> Dict[str, str]:
    if not CONFIG_ENV_PATH.exists():
        return {}

    result: Dict[str, str] = {}
    for raw_line in CONFIG_ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        result[key.strip()] = value.strip()
    return result


def _mask_value(value: Any) -> str:
    text = '' if value is None else str(value)
    if not text:
        return '未配置'
    if len(text) <= 6:
        return '*' * len(text)
    return f'{text[:3]}***{text[-3:]}'


def _validate_config_value(config_key: str, value: str | None, config_item: Dict[str, Any]) -> Dict[str, str]:
    if config_item.get('is_required') and not (value or '').strip():
        return {'status': 'failed', 'message': '必填配置不能为空'}
    if not value:
        return {'status': 'warning', 'message': '未提供值，沿用现有配置'}

    input_type = str(cast(Dict[str, Any], config_item.get('schema_json') or {}).get('input') or '')
    if 'base_url' in config_key or input_type == 'url':
        parsed = urlparse(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            return {'status': 'failed', 'message': 'URL 配置必须以 http/https 开头'}
    if input_type == 'file':
        try:
            json.loads(value)
        except json.JSONDecodeError:
            return {'status': 'failed', 'message': '文件类配置当前要求提供 JSON 文本内容'}
    return {'status': 'success', 'message': '验证通过'}


def _load_llm_config() -> Dict[str, Any]:
    if not LLM_CONFIG_PATH.exists():
        return {}
    return runpy.run_path(str(LLM_CONFIG_PATH))


def _build_system_configs() -> List[Dict[str, Any]]:
    _ensure_foundation_tables()
    env = _load_config_env()
    llm_globals = _load_llm_config()
    env_updated_at = _isoformat_timestamp(CONFIG_ENV_PATH)
    llm_updated_at = _isoformat_timestamp(LLM_CONFIG_PATH)
    cookies_path = Path(env.get('MIAOSHOU_COOKIES_FILE', '')) if env.get('MIAOSHOU_COOKIES_FILE') else None
    cookies_updated_at = _isoformat_timestamp(cookies_path) if cookies_path else None

    items: List[Dict[str, Any]] = [
        {
            'config_key': 'database.host',
            'config_name': '数据库主机',
            'category': 'database',
            'environment': 'prod',
            'value_type': 'string',
            'secret_level': 'masked',
            'value_masked': env.get('DB_HOST', '未配置'),
            'description': 'Ops API 连接 PostgreSQL 使用的主机地址。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if env.get('DB_HOST') else 'warning',
            'last_verified_at': env_updated_at,
            'last_verify_message': '来自 config.env',
            'updated_at': env_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'text'},
            'dependency_json': {'sources': ['config/config.env'], 'services': ['ops-api', 'workflow scripts']},
            'file_info': None,
            'recent_changes': [],
        },
        {
            'config_key': 'database.password',
            'config_name': '数据库密码',
            'category': 'database',
            'environment': 'prod',
            'value_type': 'password',
            'secret_level': 'critical',
            'value_masked': _mask_value(env.get('DB_PASSWORD')),
            'description': 'PostgreSQL 密码，前端只展示掩码。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if env.get('DB_PASSWORD') else 'warning',
            'last_verified_at': env_updated_at,
            'last_verify_message': '来自 config.env',
            'updated_at': env_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'password'},
            'dependency_json': {'sources': ['config/config.env'], 'services': ['ops-api']},
            'file_info': None,
            'recent_changes': [],
        },
        {
            'config_key': 'llm.default.api_key',
            'config_name': '默认 LLM API Key',
            'category': 'llm',
            'environment': 'prod',
            'value_type': 'password',
            'secret_level': 'critical',
            'value_masked': _mask_value(env.get('LLM_API_KEY') or llm_globals.get('LLM_API_KEY')),
            'description': '默认文本模型接口密钥。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if (env.get('LLM_API_KEY') or llm_globals.get('LLM_API_KEY')) else 'warning',
            'last_verified_at': env_updated_at or llm_updated_at,
            'last_verify_message': '来自 config.env / llm_config.py',
            'updated_at': env_updated_at or llm_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'password'},
            'dependency_json': {'sources': ['config/config.env', 'config/llm_config.py'], 'services': ['listing-optimizer', 'profit-analyzer']},
            'file_info': None,
            'recent_changes': [],
        },
        {
            'config_key': 'llm.default.base_url',
            'config_name': '默认 LLM Base URL',
            'category': 'llm',
            'environment': 'prod',
            'value_type': 'string',
            'secret_level': 'masked',
            'value_masked': env.get('LLM_BASE_URL') or str(llm_globals.get('LLM_BASE_URL') or '未配置'),
            'description': 'LLM 默认请求入口。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if (env.get('LLM_BASE_URL') or llm_globals.get('LLM_BASE_URL')) else 'warning',
            'last_verified_at': env_updated_at or llm_updated_at,
            'last_verify_message': '来自 config.env / llm_config.py',
            'updated_at': env_updated_at or llm_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'text'},
            'dependency_json': {'sources': ['config/config.env', 'config/llm_config.py'], 'services': ['all llm tasks']},
            'file_info': None,
            'recent_changes': [],
        },
        {
            'config_key': 'feishu.webhook.default',
            'config_name': '飞书 Webhook',
            'category': 'feishu',
            'environment': 'prod',
            'value_type': 'password',
            'secret_level': 'secret',
            'value_masked': _mask_value(env.get('FEISHU_WEBHOOK_URL')),
            'description': '默认飞书机器人 webhook。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if env.get('FEISHU_WEBHOOK_URL') else 'warning',
            'last_verified_at': env_updated_at,
            'last_verify_message': '来自 config.env',
            'updated_at': env_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'password'},
            'dependency_json': {'sources': ['config/config.env'], 'services': ['notification_service', 'heartbeat scripts']},
            'file_info': None,
            'recent_changes': [],
        },
        {
            'config_key': 'feishu.app_secret',
            'config_name': '飞书 App Secret',
            'category': 'feishu',
            'environment': 'prod',
            'value_type': 'password',
            'secret_level': 'critical',
            'value_masked': _mask_value(env.get('FEISHU_APP_SECRET')),
            'description': '飞书 tenant_access_token 获取密钥。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if env.get('FEISHU_APP_SECRET') else 'warning',
            'last_verified_at': env_updated_at,
            'last_verify_message': '来自 config.env',
            'updated_at': env_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'password'},
            'dependency_json': {'sources': ['config/config.env'], 'services': ['notification_service', 'feishu integrations']},
            'file_info': None,
            'recent_changes': [],
        },
        {
            'config_key': 'miaoshou.cookies.file',
            'config_name': '妙手 ERP Cookies 文件',
            'category': 'cookies',
            'environment': 'prod',
            'value_type': 'file',
            'secret_level': 'critical',
            'value_masked': str(cookies_path) if cookies_path else '未配置',
            'description': '妙手采集与回写流程依赖的 cookies 文件路径。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if cookies_path and cookies_path.exists() else 'warning',
            'last_verified_at': cookies_updated_at,
            'last_verify_message': '文件存在' if cookies_path and cookies_path.exists() else '文件缺失',
            'updated_at': cookies_updated_at or env_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'file', 'accepted_types': ['application/json']},
            'dependency_json': {'sources': ['config/config.env'], 'services': ['miaoshou-collector', 'cookies_alert.sh']},
            'file_info': {
                'file_name': cookies_path.name if cookies_path else None,
                'exists': bool(cookies_path and cookies_path.exists()),
                'path': str(cookies_path) if cookies_path else None,
            },
            'recent_changes': [],
        },
        {
            'config_key': 'local1688.url',
            'config_name': '本地 1688 服务地址',
            'category': 'integration',
            'environment': 'prod',
            'value_type': 'string',
            'secret_level': 'masked',
            'value_masked': env.get('LOCAL_1688_URL', '未配置'),
            'description': '本地 1688 服务入口。',
            'is_required': True,
            'is_active': True,
            'last_verify_status': 'success' if env.get('LOCAL_1688_URL') else 'warning',
            'last_verified_at': env_updated_at,
            'last_verify_message': '来自 config.env',
            'updated_at': env_updated_at,
            'updated_by': 'system',
            'expires_at': None,
            'schema_json': {'input': 'text'},
            'dependency_json': {'sources': ['config/config.env'], 'services': ['local-1688-weight']},
            'file_info': None,
            'recent_changes': [],
        },
    ]

    overrides: Dict[Tuple[str, str], Dict[str, Any]] = {}
    change_logs: Dict[int, List[Dict[str, Any]]] = {}

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                config_key,
                config_name,
                category,
                environment,
                value_type,
                secret_level,
                value_masked,
                description,
                schema_json,
                dependency_json,
                is_required,
                is_active,
                expires_at,
                last_verified_at,
                last_verify_status,
                last_verify_message,
                updated_at,
                updated_by
            FROM system_configs
            ORDER BY updated_at DESC NULLS LAST, id DESC
            """
        )
        for row in cast(List[Dict[str, Any]], list(cur.fetchall())):
            overrides[(str(row['config_key']), str(row['environment']))] = row

        cur.execute(
            """
            SELECT
                l.id,
                l.config_id,
                l.action_type,
                l.change_reason,
                l.verify_status,
                l.verify_message,
                l.operator_name,
                l.created_at
            FROM config_change_logs l
            INNER JOIN (
                SELECT id FROM system_configs
            ) c ON c.id = l.config_id
            ORDER BY l.created_at DESC
            """
        )
        for row in cast(List[Dict[str, Any]], list(cur.fetchall())):
            config_id = int(row['config_id'])
            change_logs.setdefault(config_id, []).append({
                'id': row.get('id'),
                'action_type': row.get('action_type'),
                'change_reason': row.get('change_reason'),
                'verify_status': row.get('verify_status'),
                'verify_message': row.get('verify_message'),
                'operator_name': row.get('operator_name'),
                'created_at': row.get('created_at'),
            })

    merged_items: List[Dict[str, Any]] = []
    seen_keys: set[Tuple[str, str]] = set()

    for item in items:
        key = (str(item['config_key']), str(item['environment']))
        override = overrides.get(key)
        if override:
            merged = deepcopy(item)
            merged.update({
                'id': override.get('id'),
                'config_name': override.get('config_name') or merged['config_name'],
                'category': override.get('category') or merged['category'],
                'value_type': override.get('value_type') or merged['value_type'],
                'secret_level': override.get('secret_level') or merged['secret_level'],
                'value_masked': override.get('value_masked') or merged.get('value_masked'),
                'description': override.get('description') or merged.get('description'),
                'schema_json': override.get('schema_json') or merged.get('schema_json'),
                'dependency_json': override.get('dependency_json') or merged.get('dependency_json'),
                'is_required': override.get('is_required', merged.get('is_required')),
                'is_active': override.get('is_active', merged.get('is_active')),
                'expires_at': override.get('expires_at'),
                'last_verified_at': override.get('last_verified_at') or merged.get('last_verified_at'),
                'last_verify_status': override.get('last_verify_status') or merged.get('last_verify_status'),
                'last_verify_message': override.get('last_verify_message') or merged.get('last_verify_message'),
                'updated_at': override.get('updated_at') or merged.get('updated_at'),
                'updated_by': override.get('updated_by') or merged.get('updated_by'),
                'recent_changes': change_logs.get(int(override['id']), merged.get('recent_changes', [])),
            })
            item = merged
        merged_items.append(item)
        seen_keys.add(key)

    for key, override in overrides.items():
        if key in seen_keys:
            continue
        merged_items.append({
            'id': override.get('id'),
            'config_key': override.get('config_key'),
            'config_name': override.get('config_name'),
            'category': override.get('category'),
            'environment': override.get('environment'),
            'value_type': override.get('value_type'),
            'secret_level': override.get('secret_level'),
            'value_masked': override.get('value_masked'),
            'description': override.get('description'),
            'is_required': override.get('is_required', True),
            'is_active': override.get('is_active', True),
            'last_verify_status': override.get('last_verify_status'),
            'last_verified_at': override.get('last_verified_at'),
            'last_verify_message': override.get('last_verify_message'),
            'updated_at': override.get('updated_at'),
            'updated_by': override.get('updated_by'),
            'expires_at': override.get('expires_at'),
            'schema_json': override.get('schema_json') or {},
            'dependency_json': override.get('dependency_json') or {},
            'file_info': None,
            'recent_changes': change_logs.get(int(override['id']), []),
        })

    items = merged_items

    for item in items:
        dependency_json = cast(Dict[str, Any], item.get('dependency_json') or {})
        source_files = cast(List[str], dependency_json.get('sources') or [])
        dependent_services = cast(List[str], dependency_json.get('services') or [])
        item['source_files'] = source_files
        item['dependent_services'] = dependent_services
        if not item.get('recent_changes'):
            item['recent_changes'] = [
                {
                    'action_type': 'sync',
                    'change_reason': f"从 {', '.join(source_files) if source_files else '配置源'} 同步只读快照",
                    'verify_status': item.get('last_verify_status'),
                    'verify_message': item.get('last_verify_message'),
                    'operator_name': item.get('updated_by') or 'system',
                    'created_at': item.get('updated_at') or item.get('last_verified_at'),
                }
            ]
    return items


def _fetch_media_assets_for_product(product_id: int) -> Dict[str, List[Dict[str, Any]]]:
    _ensure_foundation_tables()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                m.id,
                m.owner_type,
                m.owner_id,
                m.media_type,
                m.usage_type,
                m.file_name,
                m.mime_type,
                m.file_size_bytes,
                m.sort_order,
                m.status,
                m.oss_url,
                m.uploaded_at,
                NULL::bigint AS sku_id,
                NULL::text AS sku_name
            FROM media_assets m
            WHERE m.owner_type = 'product'
              AND m.owner_id = %s
              AND COALESCE(m.is_deleted, 0) = 0
            ORDER BY m.sort_order ASC, m.id ASC
            """,
            (product_id,),
        )
        main_assets = cast(List[Dict[str, Any]], list(cur.fetchall()))

        cur.execute(
            """
            SELECT
                m.id,
                m.owner_type,
                m.owner_id,
                m.media_type,
                m.usage_type,
                m.file_name,
                m.mime_type,
                m.file_size_bytes,
                m.sort_order,
                m.status,
                m.oss_url,
                m.uploaded_at,
                s.id AS sku_id,
                s.sku_name
            FROM media_assets m
            INNER JOIN product_skus s ON s.id = m.owner_id
            WHERE m.owner_type = 'product_sku'
              AND s.product_id = %s
              AND COALESCE(m.is_deleted, 0) = 0
              AND COALESCE(s.is_deleted, 0) = 0
            ORDER BY m.sort_order ASC, m.id ASC
            """,
            (product_id,),
        )
        sku_assets = cast(List[Dict[str, Any]], list(cur.fetchall()))

    return {
        'main_media_assets': [{**asset, 'asset_url': _media_content_path(int(asset['id']))} for asset in main_assets],
        'sku_media_assets': [{**asset, 'asset_url': _media_content_path(int(asset['id']))} for asset in sku_assets],
    }


def _sync_product_media_columns(cur: Any, product_id: int) -> None:
    cur.execute(
        """
        SELECT id, file_name, uploaded_at
        FROM media_assets
        WHERE owner_type = 'product'
          AND owner_id = %s
          AND COALESCE(is_deleted, 0) = 0
        ORDER BY sort_order ASC, id ASC
        """,
        (product_id,),
    )
    main_rows = cast(List[Dict[str, Any]], list(cur.fetchall()))
    main_images: List[Dict[str, Any]] = [
        {
            'media_asset_id': int(row['id']),
            'url': _media_content_path(int(row['id'])),
            'file_name': row.get('file_name'),
            'uploaded_at': _serialize_datetime(row.get('uploaded_at')),
            'usage_type': 'main_image',
        }
        for row in main_rows
    ]

    cur.execute(
        """
        SELECT m.id, m.file_name, m.uploaded_at, s.id AS sku_id
        FROM media_assets m
        INNER JOIN product_skus s ON s.id = m.owner_id
        WHERE m.owner_type = 'product_sku'
          AND s.product_id = %s
          AND COALESCE(m.is_deleted, 0) = 0
          AND COALESCE(s.is_deleted, 0) = 0
        ORDER BY m.sort_order ASC, m.id ASC
        """,
        (product_id,),
    )
    sku_rows = cast(List[Dict[str, Any]], list(cur.fetchall()))
    sku_images: List[Dict[str, Any]] = [
        {
            'media_asset_id': int(row['id']),
            'url': _media_content_path(int(row['id'])),
            'file_name': row.get('file_name'),
            'uploaded_at': _serialize_datetime(row.get('uploaded_at')),
            'usage_type': 'sku_image',
            'sku_id': row.get('sku_id'),
        }
        for row in sku_rows
    ]

    cur.execute(
        "UPDATE products SET main_images = %s, sku_images = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (Json(main_images), Json(sku_images), product_id),
    )


def _paginate(base_sql: str, count_sql: str, params: Tuple[Any, ...], page: int, page_size: int) -> Dict[str, Any]:
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(count_sql, params)
        count_row = cast(Dict[str, Any] | None, cur.fetchone())
        total = int((count_row or {}).get('total', 0))
        cur.execute(f"{base_sql} LIMIT %s OFFSET %s", params + (page_size, offset))
        items = cast(List[Dict[str, Any]], list(cur.fetchall()))
    return {
        'items': items,
        'page': page,
        'page_size': page_size,
        'total': total,
        'has_more': offset + len(items) < total,
    }


def _paginate_items(items: List[Dict[str, Any]], page: int, page_size: int) -> Dict[str, Any]:
    offset = max(page - 1, 0) * page_size
    sliced = items[offset:offset + page_size]
    return {
        'items': sliced,
        'page': page,
        'page_size': page_size,
        'total': len(items),
        'has_more': offset + len(sliced) < len(items),
    }


def _service_stub(agent_id: int) -> Dict[str, Any] | None:
    for service in SERVICE_CATALOG:
        if service['id'] == agent_id:
            return deepcopy(service)
    return None


def fetch_agents(page: int = 1, page_size: int = 50, status: str | None = None, agent_type: str | None = None, keyword: str | None = None) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE LOWER(COALESCE(exec_state, '')) IN ('new', 'error_fix_pending', 'normal_crash')) AS pending_task_count,
                COUNT(*) FILTER (WHERE LOWER(COALESCE(exec_state, '')) = 'processing') AS processing_task_count
            FROM tasks
            """
        )
        task_stats = cast(Dict[str, Any], cur.fetchone() or {})
        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE LOWER(COALESCE(run_status, '')) = 'failed') AS failed_24h_count
            FROM main_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
            """
        )
        failure_stats = cast(Dict[str, Any], cur.fetchone() or {})
        cur.execute(
            """
            SELECT heartbeat_status, report_time
            FROM heartbeat_events
            ORDER BY report_time DESC
            LIMIT 1
            """
        )
        heartbeat_stats = cast(Dict[str, Any], cur.fetchone() or {})

    items: List[Dict[str, Any]] = []
    for service in SERVICE_CATALOG:
        row = deepcopy(service)
        if service['id'] == ECOMMERCE_SERVICE_ID:
            row['pending_task_count'] = task_stats.get('pending_task_count', 0)
            row['processing_task_count'] = task_stats.get('processing_task_count', 0)
            row['failed_24h_count'] = failure_stats.get('failed_24h_count', 0)
            row['last_heartbeat_status'] = heartbeat_stats.get('heartbeat_status')
            row['updated_at'] = heartbeat_stats.get('report_time')
        else:
            row['pending_task_count'] = 0
            row['processing_task_count'] = 0
            row['failed_24h_count'] = 0
            row['last_heartbeat_status'] = None
            row['updated_at'] = None
        items.append(row)

    if status:
        items = [item for item in items if item['status'] == status]
    if agent_type:
        items = [item for item in items if item['type'] == agent_type]
    if keyword:
        needle = keyword.lower()
        items = [
            item for item in items
            if needle in item['code'].lower()
            or needle in item['name'].lower()
            or needle in (item.get('description') or '').lower()
        ]

    return _paginate_items(items, page, page_size)


def fetch_agent(agent_id: int) -> Dict[str, Any] | None:
    return _service_stub(agent_id)


def fetch_agent_components(agent_id: int) -> List[Dict[str, Any]]:
    if agent_id != ECOMMERCE_SERVICE_ID:
        return []

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            WITH task_counts AS (
                SELECT
                    COALESCE(agent_code, 'system-unclassified') AS component_code,
                    COALESCE(agent_name, 'System Unclassified') AS component_name,
                    COUNT(*) AS task_count,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(exec_state, '')) IN ('new', 'error_fix_pending', 'normal_crash')) AS pending_task_count,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(exec_state, '')) = 'processing') AS processing_task_count,
                    MAX(updated_at) AS last_task_at
                FROM v_agent_tasks
                GROUP BY 1, 2
            ),
            log_counts AS (
                SELECT
                    COALESCE(agent_code, 'system-unclassified') AS component_code,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(run_status, '')) = 'failed' AND created_at > NOW() - INTERVAL '24 hours') AS failed_24h_count,
                    MAX(created_at) AS last_log_at
                FROM v_agent_logs
                GROUP BY 1
            ),
            heartbeat_counts AS (
                SELECT
                    COALESCE(agent_code, 'system-unclassified') AS component_code,
                    (ARRAY_AGG(heartbeat_status ORDER BY report_time DESC))[1] AS last_heartbeat_status,
                    MAX(report_time) AS last_heartbeat_at
                FROM v_agent_heartbeats
                GROUP BY 1
            )
            SELECT
                t.component_code AS code,
                t.component_name AS name,
                'component' AS type,
                CASE
                    WHEN COALESCE(h.last_heartbeat_status, '') = 'critical' OR COALESCE(l.failed_24h_count, 0) > 0 THEN 'degraded'
                    WHEN COALESCE(t.processing_task_count, 0) > 0 THEN 'busy'
                    ELSE 'active'
                END AS status,
                t.task_count,
                COALESCE(t.pending_task_count, 0) AS pending_task_count,
                COALESCE(t.processing_task_count, 0) AS processing_task_count,
                COALESCE(l.failed_24h_count, 0) AS failed_24h_count,
                h.last_heartbeat_status,
                GREATEST(
                    COALESCE(t.last_task_at, TIMESTAMP 'epoch'),
                    COALESCE(l.last_log_at, TIMESTAMP 'epoch'),
                    COALESCE(h.last_heartbeat_at, TIMESTAMP 'epoch')
                ) AS updated_at
            FROM task_counts t
            LEFT JOIN log_counts l ON l.component_code = t.component_code
            LEFT JOIN heartbeat_counts h ON h.component_code = t.component_code
            ORDER BY pending_task_count DESC, processing_task_count DESC, failed_24h_count DESC, code ASC
            """
        )
        return cast(List[Dict[str, Any]], list(cur.fetchall()))


def fetch_agent_tasks(
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
) -> Dict[str, Any]:
    if agent_id != ECOMMERCE_SERVICE_ID:
        return _paginate_items([], page, page_size)

    where = ["1=1"]
    params: List[Any] = []

    if exec_state:
        where.append("LOWER(COALESCE(t.exec_state, '')) = LOWER(%s)")
        params.append(exec_state)
    if status:
        where.append("LOWER(COALESCE(t.status, '')) = LOWER(%s)")
        params.append(status)
    if task_type:
        where.append("t.task_type = %s")
        params.append(task_type)
    if priority:
        where.append("t.priority = %s")
        params.append(priority)
    if task_level is not None:
        where.append("t.task_level = %s")
        params.append(task_level)
    if keyword:
        like = f"%{keyword}%"
        where.append("(t.task_name ILIKE %s OR COALESCE(t.display_name, '') ILIKE %s OR COALESCE(t.last_error, '') ILIKE %s)")
        params.extend([like, like, like])
    if component_code:
        where.append("COALESCE(vat.agent_code, 'system-unclassified') = %s")
        params.append(component_code)

    where_sql = ' AND '.join(where)
    base_sql = f"""
        SELECT
            t.task_name,
            {ECOMMERCE_SERVICE_ID} AS agent_id,
            'e-commerce' AS agent_code,
            'E-commerce' AS agent_name,
            COALESCE(vat.agent_code, 'system-unclassified') AS component_code,
            COALESCE(vat.agent_name, 'System Unclassified') AS component_name,
            t.display_name,
            t.task_type,
            t.priority,
            t.status,
            t.exec_state,
            t.current_stage,
            t.stage_status,
            t.stage_result,
            t.task_level,
            t.parent_task_id,
            t.root_task_id,
            t.retry_count,
            t.last_error,
            t.notification_status,
            t.feedback_doc_url,
            t.feedback_markdown_file,
            t.created_at,
            t.updated_at
        FROM tasks t
        LEFT JOIN v_agent_tasks vat ON vat.task_name = t.task_name
        WHERE {where_sql}
        ORDER BY t.created_at DESC
    """
    count_sql = f"SELECT COUNT(*) AS total FROM tasks t LEFT JOIN v_agent_tasks vat ON vat.task_name = t.task_name WHERE {where_sql}"
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_agent_logs(
    agent_id: int,
    page: int = 1,
    page_size: int = 200,
    task_name: str | None = None,
    run_status: str | None = None,
    log_type: str | None = None,
    component_code: str | None = None,
) -> Dict[str, Any]:
    if agent_id != ECOMMERCE_SERVICE_ID:
        return _paginate_items([], page, page_size)

    where = ["1=1"]
    params: List[Any] = []

    if task_name:
        where.append("l.task_name = %s")
        params.append(task_name)
    if run_status:
        where.append("LOWER(COALESCE(l.run_status, '')) = LOWER(%s)")
        params.append(run_status)
    if log_type:
        where.append("LOWER(COALESCE(l.log_type, '')) = LOWER(%s)")
        params.append(log_type)
    if component_code:
        where.append("COALESCE(vl.agent_code, 'system-unclassified') = %s")
        params.append(component_code)

    where_sql = ' AND '.join(where)
    base_sql = f"""
        SELECT
            l.id AS log_id,
            {ECOMMERCE_SERVICE_ID} AS agent_id,
            'e-commerce' AS agent_code,
            'E-commerce' AS agent_name,
            COALESCE(vl.agent_code, 'system-unclassified') AS component_code,
            COALESCE(vl.agent_name, 'System Unclassified') AS component_name,
            l.task_name,
            l.log_type,
            l.log_level,
            l.run_status,
            l.run_message,
            l.run_content,
            l.duration_ms,
            l.run_start_time,
            l.run_end_time,
            l.created_at
        FROM main_logs l
        LEFT JOIN v_agent_logs vl ON vl.log_id = l.id
        WHERE {where_sql}
        ORDER BY l.created_at DESC
    """
    count_sql = f"SELECT COUNT(*) AS total FROM main_logs l LEFT JOIN v_agent_logs vl ON vl.log_id = l.id WHERE {where_sql}"
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_agent_heartbeats(
    agent_id: int,
    page: int = 1,
    page_size: int = 100,
    status: str | None = None,
) -> Dict[str, Any]:
    if agent_id != ECOMMERCE_SERVICE_ID:
        return _paginate_items([], page, page_size)

    where = ["1=1"]
    params: List[Any] = []

    if status:
        where.append("h.heartbeat_status = %s")
        params.append(status)

    where_sql = ' AND '.join(where)
    base_sql = f"""
        SELECT
            h.id AS heartbeat_id,
            {ECOMMERCE_SERVICE_ID} AS agent_id,
            'e-commerce' AS agent_code,
            'E-commerce' AS agent_name,
            h.heartbeat_status,
            h.summary,
            h.pending_count,
            h.processing_count,
            h.requires_manual_count,
            h.overtime_temp_count,
            h.failed_recent_count,
            h.duration_ms,
            h.host_name,
            h.report_time,
            h.created_at
        FROM heartbeat_events h
        WHERE {where_sql}
        ORDER BY h.report_time DESC
    """
    count_sql = f"SELECT COUNT(*) AS total FROM heartbeat_events h WHERE {where_sql}"
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_dashboard_overview() -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                3 AS agent_count,
                3 AS active_agent_count,
                (SELECT COUNT(*) FROM tasks WHERE LOWER(COALESCE(exec_state, '')) IN ('new', 'error_fix_pending', 'normal_crash')) AS pending_task_count,
                (SELECT COUNT(*) FROM tasks WHERE LOWER(COALESCE(exec_state, '')) = 'processing') AS processing_task_count,
                (SELECT COUNT(*) FROM tasks WHERE LOWER(COALESCE(exec_state, '')) = 'requires_manual') AS manual_task_count,
                (SELECT COUNT(*) FROM tasks WHERE task_type = '临时任务' AND LOWER(COALESCE(exec_state, '')) = 'processing') AS overtime_temp_count,
                (SELECT CASE WHEN EXISTS (
                    SELECT 1 FROM heartbeat_events WHERE heartbeat_status = 'warning' AND report_time > NOW() - INTERVAL '24 hours'
                ) THEN 1 ELSE 0 END) AS heartbeat_warning_agent_count,
                (SELECT CASE WHEN EXISTS (
                    SELECT 1 FROM heartbeat_events WHERE heartbeat_status = 'critical' AND report_time > NOW() - INTERVAL '24 hours'
                ) THEN 1 ELSE 0 END) AS heartbeat_critical_agent_count,
                (SELECT COUNT(*) FILTER (WHERE LOWER(COALESCE(run_status, '')) = 'success')::FLOAT /
                        NULLIF(COUNT(*), 0)
                 FROM main_logs
                 WHERE created_at > NOW() - INTERVAL '24 hours'
                ) AS task_success_rate_24h
            """
        )
        overview = cast(Dict[str, Any], cur.fetchone() or {})
        overview.update(_fetch_task_lifecycle_metrics(cur))
        stage_distribution = cast(Dict[str, int], overview.get('stage_distribution') or {})
        stage_status_distribution = cast(Dict[str, int], overview.get('stage_status_distribution') or {})
        overview['retrospective_task_count'] = int(stage_distribution.get('retrospective', 0))
        overview['blocked_stage_count'] = int(stage_status_distribution.get('blocked', 0))
        return overview


def fetch_task(task_name: str) -> Dict[str, Any] | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                t.task_name,
                {ECOMMERCE_SERVICE_ID} AS agent_id,
                'e-commerce' AS agent_code,
                'E-commerce' AS agent_name,
                COALESCE(vat.agent_code, 'system-unclassified') AS component_code,
                COALESCE(vat.agent_name, 'System Unclassified') AS component_name,
                t.display_name,
                t.task_type,
                t.priority,
                t.status,
                t.exec_state,
                t.current_stage,
                t.stage_status,
                t.stage_result,
                t.task_level,
                t.parent_task_id,
                t.root_task_id,
                t.retry_count,
                t.last_error,
                t.progress_checkpoint,
                t.notification_status,
                t.feedback_doc_url,
                t.feedback_markdown_file,
                t.created_at,
                t.updated_at
            FROM tasks t
            LEFT JOIN v_agent_tasks vat ON vat.task_name = t.task_name
            WHERE t.task_name = %s
            """,
            (task_name,),
        )
        return cast(Dict[str, Any] | None, cur.fetchone())


def fetch_full_listing_recent_tasks(
    page: int = 1,
    page_size: int = 20,
    exec_state: str | None = None,
    priority: str | None = None,
    lightweight: bool | None = None,
    publish: bool | None = None,
    keyword: str | None = None,
) -> Dict[str, Any]:
    where = ["LOWER(COALESCE(t.task_type, '')) = '临时任务'", "t.task_name LIKE 'AUTO-LISTING-%%'"]
    params: List[Any] = []

    if exec_state:
        where.append("LOWER(COALESCE(t.exec_state, '')) = LOWER(%s)")
        params.append(exec_state)

    if priority:
        where.append("LOWER(COALESCE(t.priority, '')) = LOWER(%s)")
        params.append(priority)

    if lightweight is not None:
        where.append("COALESCE(t.progress_checkpoint ->> 'lightweight', 'false') = %s")
        params.append('true' if lightweight else 'false')

    if publish is not None:
        where.append("COALESCE(t.progress_checkpoint ->> 'no_publish', 'false') = %s")
        params.append('false' if publish else 'true')

    if keyword:
        where.append(
            """
            (
                LOWER(COALESCE(t.task_name, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.display_name, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.description, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.progress_checkpoint ->> 'url', '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.progress_checkpoint ->> 'current_step', '')) LIKE LOWER(%s)
            )
            """
        )
        fuzzy = f"%{keyword}%"
        params.extend([fuzzy, fuzzy, fuzzy, fuzzy, fuzzy])

    where_sql = ' AND '.join(where)
    base_sql = f"""
        SELECT
            t.task_name,
            t.display_name,
            t.priority,
            t.exec_state,
            t.current_stage,
            t.stage_status,
            t.updated_at,
            COALESCE(NULLIF(t.progress_checkpoint ->> 'product_count', '')::INT, 0) AS product_count,
            CASE WHEN COALESCE(t.progress_checkpoint ->> 'lightweight', 'false') = 'true' THEN TRUE ELSE FALSE END AS lightweight,
            CASE WHEN COALESCE(t.progress_checkpoint ->> 'no_publish', 'false') = 'true' THEN FALSE ELSE TRUE END AS publish,
            t.progress_checkpoint ->> 'current_step' AS current_step,
            t.progress_checkpoint ->> 'url' AS first_url
        FROM tasks t
        WHERE {where_sql}
        ORDER BY t.created_at DESC
    """
    count_sql = f"SELECT COUNT(*) AS total FROM tasks t WHERE {where_sql}"
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_profit_analysis_summary(site: str | None = None) -> Dict[str, Any]:
    _ensure_foundation_tables()
    where = ["COALESCE(pa.is_deleted, 0) = 0"]
    params: List[Any] = []
    normalized_site_code = _normalize_site_code_value(site)
    if normalized_site_code:
        where.append(f"LOWER({_profit_analysis_site_code_expr('pa')}) = LOWER(%s)")
        params.append(normalized_site_code)

    where_sql = ' AND '.join(where)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT pa.product_id) AS total_products,
                COUNT(DISTINCT pa.sku_id) AS total_skus,
                AVG(pa.profit_rate) AS avg_profit_rate,
                AVG(pa.total_cost_cny) AS avg_total_cost_cny,
                AVG(COALESCE(pa.estimated_profit_local, pa.estimated_profit_cny)) AS avg_estimated_profit_local,
                AVG(pa.estimated_profit_cny) AS avg_estimated_profit_cny,
                AVG(COALESCE(pa.new_store_price, pa.new_store_price_twd, pa.suggested_price_twd)) AS avg_suggested_price_local,
                AVG(pa.suggested_price_twd) AS avg_suggested_price_twd,
                MIN(COALESCE(pa.currency, mc.default_currency, 'TWD')) AS currency,
                COUNT(*) FILTER (WHERE COALESCE(pa.profit_rate, 0) > 0.3) AS high_profit_count,
                COUNT(*) FILTER (WHERE COALESCE(pa.profit_rate, 0) > 0.15 AND COALESCE(pa.profit_rate, 0) <= 0.3) AS medium_profit_count,
                COUNT(*) FILTER (WHERE COALESCE(pa.profit_rate, 0) > 0 AND COALESCE(pa.profit_rate, 0) <= 0.15) AS low_profit_count,
                COUNT(*) FILTER (WHERE COALESCE(pa.profit_rate, 0) <= 0) AS loss_count,
                MAX(COALESCE(pa.updated_at, pa.created_at)) AS last_analysis_at
            FROM product_analysis pa
            LEFT JOIN market_configs mc ON LOWER(mc.market_code) = LOWER({_profit_analysis_market_code_expr('pa')})
            WHERE {where_sql}
            """,
            tuple(params),
        )
        row = cast(Dict[str, Any] | None, cur.fetchone()) or {}
    return row


def fetch_profit_analysis_items(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    site: str | None = None,
    profit_rate_min: float | None = None,
    profit_rate_max: float | None = None,
) -> Dict[str, Any]:
    _ensure_foundation_tables()
    where = ["COALESCE(pa.is_deleted, 0) = 0"]
    params: List[Any] = []
    normalized_site_code = _normalize_site_code_value(site)

    if keyword:
        fuzzy = f"%{keyword}%"
        where.append(
            """
            (
                LOWER(COALESCE(p.title, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(p.alibaba_product_id, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(p.product_id_new, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(ps.sku_name, '')) LIKE LOWER(%s)
            )
            """
        )
        params.extend([fuzzy, fuzzy, fuzzy, fuzzy])
    if normalized_site_code:
        where.append(f"LOWER({_profit_analysis_site_code_expr('pa')}) = LOWER(%s)")
        params.append(normalized_site_code)
    if profit_rate_min is not None:
        where.append("COALESCE(pa.profit_rate, 0) >= %s")
        params.append(profit_rate_min)
    if profit_rate_max is not None:
        where.append("COALESCE(pa.profit_rate, 0) <= %s")
        params.append(profit_rate_max)

    where_sql = ' AND '.join(where)
    base_sql = f"""
        SELECT
            pa.id,
            pa.product_id,
            pa.sku_id,
            COALESCE(pa.platform, 'Shopee') AS platform,
            {_profit_analysis_site_expr('pa')} AS site,
            {_profit_analysis_site_code_expr('pa')} AS site_code,
            {_profit_analysis_market_code_expr('pa')} AS market_code,
            NULL::text AS shop_code,
            p.alibaba_product_id,
            p.product_id_new,
            p.title,
            ps.sku_name,
            pa.purchase_price_cny,
            COALESCE(pa.new_store_price, pa.new_store_price_twd, pa.suggested_price_twd) AS suggested_price_local,
            pa.suggested_price_twd,
            pa.suggested_price_cny,
            COALESCE(pa.estimated_profit_local, pa.estimated_profit_cny) AS estimated_profit_local,
            pa.estimated_profit_cny,
            pa.shipping_cn,
            COALESCE(pa.hidden_shipping_cost_local, pa.sls_fee_cny) AS hidden_shipping_cost_local,
            COALESCE(pa.platform_shipping_fee_local, pa.sls_fee_twd) AS platform_shipping_fee_local,
            pa.agent_fee_cny,
            pa.sls_fee_cny,
            COALESCE(pa.commission_twd, pa.commission_cny) AS commission_local,
            pa.commission_cny,
            pa.service_fee_cny,
            pa.transaction_fee_cny,
            pa.weight_kg,
            pa.chargeable_weight_g,
            ps.package_weight,
            ps.package_length,
            ps.package_width,
            ps.package_height,
            pa.total_cost_cny,
            pa.profit_rate,
            COALESCE(pa.currency, mc.default_currency, 'TWD') AS currency,
            pa.analysis_date,
            pa.remarks,
            COALESCE(pa.updated_at, pa.created_at) AS updated_at
        FROM product_analysis pa
        LEFT JOIN products p ON p.id = pa.product_id
        LEFT JOIN product_skus ps ON ps.id = pa.sku_id
        LEFT JOIN market_configs mc ON LOWER(mc.market_code) = LOWER({_profit_analysis_market_code_expr('pa')})
        WHERE {where_sql}
        ORDER BY COALESCE(pa.updated_at, pa.created_at) DESC NULLS LAST, pa.id DESC
    """
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM product_analysis pa
        LEFT JOIN products p ON p.id = pa.product_id
        LEFT JOIN product_skus ps ON ps.id = pa.sku_id
        WHERE {where_sql}
    """
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_profit_init_candidate_summary(site: str | None = None) -> Dict[str, Any]:
    _ensure_foundation_tables()
    where = ["COALESCE(p.is_deleted, 0) = 0", "COALESCE(p.alibaba_product_id, '') <> ''"]
    params: List[Any] = []
    normalized_site_code = _normalize_site_code_value(site)
    if normalized_site_code:
        params.append(normalized_site_code)

    site_filter = f"LOWER({_profit_analysis_site_code_expr('pa')}) = LOWER(%s) AND" if normalized_site_code else ''
    where_sql = ' AND '.join(where)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COUNT(DISTINCT p.id) AS total_products,
                COUNT(DISTINCT CASE WHEN pa.id IS NOT NULL THEN p.id END) AS initialized_products,
                COUNT(DISTINCT CASE WHEN pa.id IS NULL THEN p.id END) AS missing_products
            FROM products p
            LEFT JOIN product_analysis pa
              ON pa.product_id = p.id
             AND {site_filter}
                 COALESCE(pa.is_deleted, 0) = 0
            WHERE {where_sql}
            """,
            tuple(params),
        )
        row = cast(Dict[str, Any] | None, cur.fetchone()) or {}
    return row


def fetch_profit_init_recent_tasks(
    page: int = 1,
    page_size: int = 20,
    exec_state: str | None = None,
    priority: str | None = None,
    keyword: str | None = None,
) -> Dict[str, Any]:
    where = ["LOWER(COALESCE(t.task_type, '')) = '临时任务'", "t.task_name LIKE 'INIT-PROFIT-%%'"]
    params: List[Any] = []
    if exec_state:
        where.append("LOWER(COALESCE(t.exec_state, '')) = LOWER(%s)")
        params.append(exec_state)
    if priority:
        where.append("LOWER(COALESCE(t.priority, '')) = LOWER(%s)")
        params.append(priority)
    if keyword:
        fuzzy = f"%{keyword}%"
        where.append(
            """
            (
                LOWER(COALESCE(t.task_name, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.display_name, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.description, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.progress_checkpoint ->> 'scope', '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.progress_checkpoint ->> 'current_step', '')) LIKE LOWER(%s)
            )
            """
        )
        params.extend([fuzzy, fuzzy, fuzzy, fuzzy, fuzzy])

    where_sql = ' AND '.join(where)
    base_sql = f"""
        SELECT
            t.task_name,
            t.display_name,
            t.priority,
            t.exec_state,
            t.current_stage,
            t.stage_status,
            t.updated_at,
            COALESCE(NULLIF(t.progress_checkpoint ->> 'candidate_count', '')::INT, 0) AS product_count,
            t.progress_checkpoint ->> 'scope' AS scope,
            t.progress_checkpoint ->> 'site' AS site,
            t.progress_checkpoint ->> 'current_step' AS current_step
        FROM tasks t
        WHERE {where_sql}
        ORDER BY t.created_at DESC
    """
    count_sql = f"SELECT COUNT(*) AS total FROM tasks t WHERE {where_sql}"
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_profit_sync_recent_tasks(
    page: int = 1,
    page_size: int = 20,
    exec_state: str | None = None,
    priority: str | None = None,
    keyword: str | None = None,
) -> Dict[str, Any]:
    where = ["LOWER(COALESCE(t.task_type, '')) = '临时任务'", "t.task_name LIKE 'PROFIT-SYNC-%%'"]
    params: List[Any] = []
    if exec_state:
        where.append("LOWER(COALESCE(t.exec_state, '')) = LOWER(%s)")
        params.append(exec_state)
    if priority:
        where.append("LOWER(COALESCE(t.priority, '')) = LOWER(%s)")
        params.append(priority)
    if keyword:
        fuzzy = f"%{keyword}%"
        where.append(
            """
            (
                LOWER(COALESCE(t.task_name, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.display_name, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.description, '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.progress_checkpoint ->> 'first_id', '')) LIKE LOWER(%s)
                OR LOWER(COALESCE(t.progress_checkpoint ->> 'current_step', '')) LIKE LOWER(%s)
            )
            """
        )
        params.extend([fuzzy, fuzzy, fuzzy, fuzzy, fuzzy])

    where_sql = ' AND '.join(where)
    base_sql = f"""
        SELECT
            t.task_name,
            t.display_name,
            t.priority,
            t.exec_state,
            t.current_stage,
            t.stage_status,
            t.updated_at,
            COALESCE(NULLIF(t.progress_checkpoint ->> 'product_count', '')::INT, 0) AS product_count,
            COALESCE(t.progress_checkpoint ->> 'profit_rate', '') AS profit_rate,
            t.progress_checkpoint ->> 'current_step' AS current_step,
            t.progress_checkpoint ->> 'first_id' AS first_id
        FROM tasks t
        WHERE {where_sql}
        ORDER BY t.created_at DESC
    """
    count_sql = f"SELECT COUNT(*) AS total FROM tasks t WHERE {where_sql}"
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_task_logs(task_name: str, limit: int = 200) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                l.id AS log_id,
                {ECOMMERCE_SERVICE_ID} AS agent_id,
                'e-commerce' AS agent_code,
                'E-commerce' AS agent_name,
                COALESCE(vl.agent_code, 'system-unclassified') AS component_code,
                COALESCE(vl.agent_name, 'System Unclassified') AS component_name,
                l.task_name,
                l.log_type,
                l.log_level,
                l.run_status,
                l.run_message,
                l.run_content,
                l.duration_ms,
                l.run_start_time,
                l.run_end_time,
                l.created_at
            FROM main_logs l
            LEFT JOIN v_agent_logs vl ON vl.log_id = l.id
            WHERE l.task_name = %s
               OR l.task_name = LEFT(%s, 50)
            ORDER BY l.created_at DESC
            LIMIT %s
            """,
            (task_name, task_name, limit),
        )
        return cast(List[Dict[str, Any]], list(cur.fetchall()))


def fetch_dashboard_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM (
                SELECT
                    'manual_required' AS alert_type,
                    %s AS agent_id,
                    'e-commerce' AS agent_code,
                    t.task_name AS entity_key,
                    t.display_name AS title,
                    COALESCE(t.last_error, t.exec_state, 'requires_manual') AS detail,
                    t.updated_at AS happened_at
                FROM tasks t
                WHERE LOWER(COALESCE(t.exec_state, '')) = 'requires_manual'

                UNION ALL

                SELECT
                    'task_blocker' AS alert_type,
                    %s AS agent_id,
                    'e-commerce' AS agent_code,
                    t.task_name AS entity_key,
                    t.display_name AS title,
                    COALESCE(t.last_error, t.exec_state, 'error_fix_pending') AS detail,
                    t.updated_at AS happened_at
                FROM tasks t
                WHERE LOWER(COALESCE(t.exec_state, '')) IN ('error_fix_pending', 'normal_crash')

                UNION ALL

                SELECT
                    'heartbeat_alert' AS alert_type,
                    %s AS agent_id,
                    'e-commerce' AS agent_code,
                    CAST(h.id AS TEXT) AS entity_key,
                    COALESCE(h.summary, h.heartbeat_status) AS title,
                    h.heartbeat_status AS detail,
                    h.report_time AS happened_at
                FROM heartbeat_events h
                WHERE h.heartbeat_status IN ('warning', 'critical')
            ) alerts
            ORDER BY happened_at DESC
            LIMIT %s
            """,
            (ECOMMERCE_SERVICE_ID, ECOMMERCE_SERVICE_ID, ECOMMERCE_SERVICE_ID, limit),
        )
        return cast(List[Dict[str, Any]], list(cur.fetchall()))


def fetch_products(
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
) -> Dict[str, Any]:
    base_where = ['COALESCE(p.is_deleted, 0) = 0']
    base_params: List[Any] = []
    normalized_site_code = _normalize_site_code_value(site_filter)

    if keyword:
        like = f'%{keyword}%'
        base_where.append("(COALESCE(p.optimized_title, '') ILIKE %s OR COALESCE(p.title, '') ILIKE %s OR COALESCE(p.alibaba_product_id, '') ILIKE %s OR COALESCE(p.product_id_new, '') ILIKE %s)")
        base_params.extend([like, like, like, like])
    if status:
        base_where.append("LOWER(COALESCE(p.status::text, '')) = LOWER(%s)")
        base_params.append(status)
    if normalized_site_code:
        legacy_site_label = _to_legacy_site_label(normalized_site_code) or normalized_site_code.upper()
        base_where.append(
            """
            (
                COALESCE(p.published_sites, '[]'::jsonb) @> %s::jsonb
                OR COALESCE(p.published_sites, '[]'::jsonb) @> %s::jsonb
                OR COALESCE(p.site_status, '{}'::jsonb) ? %s
                OR COALESCE(p.site_status, '{}'::jsonb) ? %s
                OR EXISTS (
                    SELECT 1
                    FROM site_listings sl
                    WHERE sl.product_id = p.id
                      AND COALESCE(sl.is_deleted, 0) = 0
                                            AND LOWER(COALESCE(sl.site_code, '')) = LOWER(%s)
                )
            )
            """
        )
        base_params.extend([
            json.dumps([legacy_site_label]),
            json.dumps([normalized_site_code]),
            legacy_site_label,
            normalized_site_code,
            normalized_site_code,
        ])
    if price_min is not None:
        base_where.append(
            """
            COALESCE((
                SELECT MAX(s.price)
                FROM product_skus s
                WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
            ), 0) >= %s
            """
        )
        base_params.append(price_min)
    if price_max is not None:
        base_where.append(
            """
            COALESCE((
                SELECT MIN(s.price)
                FROM product_skus s
                WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
            ), 0) <= %s
            """
        )
        base_params.append(price_max)
    if inventory_warning_only:
        base_where.append(
            """
            COALESCE((
                SELECT SUM(COALESCE(s.stock, 0))
                FROM product_skus s
                WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
            ), 0) < 20
            """
        )
    if listing_only:
        base_where.append(
            """
            EXISTS (
                SELECT 1
                FROM (
                    SELECT sl.product_id::text AS product_ref, sl.site_code
                    FROM site_listings sl
                    WHERE sl.product_id = p.id AND COALESCE(sl.is_deleted, 0) = 0
                    UNION
                    SELECT COALESCE(pli.product_id_new, pli.alibaba_product_id) AS product_ref, 'TW' AS site_code
                    FROM product_listing_info pli
                    WHERE pli.alibaba_product_id = p.alibaba_product_id OR pli.product_id_new = p.product_id_new
                ) listing_refs
            )
            """
        )

    where = list(base_where)
    params = list(base_params)
    if quick_filter and quick_filter != 'all':
        normalized_quick_filter = quick_filter.strip().lower()
        if normalized_quick_filter in {'published', 'listed', 'optimized'}:
            where.append("LOWER(COALESCE(p.status::text, '')) = %s")
            params.append(normalized_quick_filter)
        elif normalized_quick_filter == 'warning':
            where.append(
                """
                COALESCE((
                    SELECT SUM(COALESCE(s.stock, 0))
                    FROM product_skus s
                    WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
                ), 0) < 20
                """
            )

    where_sql = ' AND '.join(where)
    base_where_sql = ' AND '.join(base_where)
    base_sql = f"""
        SELECT
            p.id,
            p.alibaba_product_id,
            p.product_id_new,
            COALESCE(NULLIF(p.optimized_title, ''), NULLIF(p.title, ''), CONCAT('商品#', p.id)) AS title,
            p.title AS original_title,
            p.status::text AS status,
            p.category,
            p.brand,
            COALESCE(p.main_images, '[]'::jsonb) AS main_images,
            COALESCE((SELECT COUNT(*) FROM product_skus s WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0), 0) AS sku_count,
            COALESCE(jsonb_array_length(COALESCE(p.main_images, '[]'::jsonb)), 0) AS main_image_count,
            COALESCE((
                SELECT SUM(COALESCE(s.stock, 0))
                FROM product_skus s
                WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
            ), 0) AS total_stock,
            COALESCE((
                SELECT COUNT(DISTINCT listing_refs.site_code)
                FROM (
                    SELECT sl.site_code
                    FROM site_listings sl
                    WHERE sl.product_id = p.id AND COALESCE(sl.is_deleted, 0) = 0
                    UNION
                    SELECT 'TW' AS site_code
                    FROM product_listing_info pli
                    WHERE pli.alibaba_product_id = p.alibaba_product_id OR pli.product_id_new = p.product_id_new
                ) listing_refs
            ), 0) AS site_listing_count,
            (
                SELECT MIN(s.price)
                FROM product_skus s
                WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
            ) AS price_min,
            (
                SELECT MAX(s.price)
                FROM product_skus s
                WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
            ) AS price_max,
            (
                SELECT MAX(pa.updated_at)
                FROM product_analysis pa
                WHERE pa.product_id = p.id AND COALESCE(pa.is_deleted, 0) = 0
            ) AS last_analysis_at,
            COALESCE(p.published_sites, '[]'::jsonb) AS published_sites,
            COALESCE(p.site_status, '{{}}'::jsonb) AS site_status,
            p.updated_at
        FROM products p
        WHERE {where_sql}
        ORDER BY p.updated_at DESC NULLS LAST, p.id DESC
    """
    count_sql = f"SELECT COUNT(*) AS total FROM products p WHERE {where_sql}"
    quick_filter_counts_sql = f"""
        SELECT
            COUNT(*) AS all_count,
            COUNT(*) FILTER (WHERE LOWER(COALESCE(p.status::text, '')) = 'published') AS published_count,
            COUNT(*) FILTER (WHERE LOWER(COALESCE(p.status::text, '')) = 'listed') AS listed_count,
            COUNT(*) FILTER (WHERE LOWER(COALESCE(p.status::text, '')) = 'optimized') AS optimized_count,
            COUNT(*) FILTER (
                WHERE COALESCE((
                    SELECT SUM(COALESCE(s.stock, 0))
                    FROM product_skus s
                    WHERE s.product_id = p.id AND COALESCE(s.is_deleted, 0) = 0
                ), 0) < 20
            ) AS warning_count
        FROM products p
        WHERE {base_where_sql}
    """
    enum_where_sql = 'COALESCE(p.is_deleted, 0) = 0'
    status_options_sql = f"""
        SELECT DISTINCT p.status::text AS status
        FROM products p
        WHERE {enum_where_sql}
          AND NULLIF(TRIM(COALESCE(p.status::text, '')), '') IS NOT NULL
        ORDER BY status ASC
    """
    site_options_sql = f"""
        SELECT DISTINCT site_code
        FROM (
            SELECT jsonb_array_elements_text(COALESCE(p.published_sites, '[]'::jsonb)) AS site_code
            FROM products p
            WHERE {enum_where_sql}
            UNION
            SELECT jsonb_object_keys(COALESCE(p.site_status, '{{}}'::jsonb)) AS site_code
            FROM products p
            WHERE {enum_where_sql}
            UNION
            SELECT sl.site_code
            FROM products p
            JOIN site_listings sl ON sl.product_id = p.id AND COALESCE(sl.is_deleted, 0) = 0
            WHERE {enum_where_sql}
        ) sites
        WHERE NULLIF(TRIM(COALESCE(site_code, '')), '') IS NOT NULL
        ORDER BY site_code ASC
    """
    offset = max(page - 1, 0) * page_size
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(count_sql, tuple(params))
        count_row = cast(Dict[str, Any] | None, cur.fetchone()) or {}
        total = int(count_row.get('total', 0))
        cur.execute(f"{base_sql} LIMIT %s OFFSET %s", tuple(params) + (page_size, offset))
        items = cast(List[Dict[str, Any]], list(cur.fetchall()))
        cur.execute(quick_filter_counts_sql, tuple(base_params))
        raw_counts = cast(Dict[str, Any] | None, cur.fetchone()) or {}
        cur.execute(status_options_sql)
        status_rows = cur.fetchall()
        cur.execute(site_options_sql)
        site_rows = cur.fetchall()
    result: Dict[str, Any] = {
        'items': items,
        'page': page,
        'page_size': page_size,
        'total': total,
        'has_more': offset + len(items) < total,
    }
    result['quick_filter_counts'] = {
        'all': int(raw_counts.get('all_count') or 0),
        'published': int(raw_counts.get('published_count') or 0),
        'listed': int(raw_counts.get('listed_count') or 0),
        'optimized': int(raw_counts.get('optimized_count') or 0),
        'warning': int(raw_counts.get('warning_count') or 0),
    }
    result['status_options'] = sorted({
        str(value)
        for value in (_extract_row_value(row, 'status') for row in status_rows)
        if value
    })
    result['site_options'] = sorted({
        str(value)
        for value in (_extract_row_value(row, 'site_code') for row in site_rows)
        if value
        for value in [_to_legacy_site_label(value)]
        if value
    })
    for item in cast(List[Dict[str, Any]], result.get('items') or []):
        item['published_sites'] = [
            normalized
            for normalized in (_to_legacy_site_label(site_code) for site_code in cast(List[Any], item.get('published_sites') or []))
            if normalized
        ]
        site_status = _as_string_dict(item.get('site_status'))
        if site_status:
            item['site_status'] = {
                normalized: value
                for raw_site, value in site_status.items()
                for normalized in [_to_legacy_site_label(raw_site)]
                if normalized
            }
        item['preview_image_url'] = _resolve_product_preview_image_url(item)
        item.pop('main_images', None)
    return result


def fetch_product(product_id: int) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                p.id,
                p.alibaba_product_id,
                p.product_id_new,
                p.created_at,
                p.updated_at,
                p.title,
                p.optimized_title,
                p.description,
                p.optimized_description,
                p.category,
                p.brand,
                p.origin,
                p.status::text AS status,
                COALESCE(p.published_sites, '[]'::jsonb) AS published_sites,
                COALESCE(p.site_status, '{}'::jsonb) AS site_status,
                COALESCE(p.main_images, '[]'::jsonb) AS main_images,
                COALESCE(p.sku_images, '[]'::jsonb) AS sku_images
            FROM products p
            WHERE p.id = %s AND COALESCE(p.is_deleted, 0) = 0
            """,
            (product_id,),
        )
        product = cast(Dict[str, Any] | None, cur.fetchone())
        if not product:
            return None

        cur.execute(
            """
            SELECT
                s.id,
                s.sku_name,
                s.shopee_sku_name,
                s.sku_code,
                s.price,
                s.stock,
                s.currency,
                s.package_weight,
                s.package_length,
                s.package_width,
                s.package_height,
                s.image_url
            FROM product_skus s
            WHERE s.product_id = %s AND COALESCE(s.is_deleted, 0) = 0
            ORDER BY s.id ASC
            """,
            (product_id,),
        )
        skus = cast(List[Dict[str, Any]], list(cur.fetchall()))

        cur.execute(
            f"""
            WITH ranked_listings AS (
                SELECT
                    CONCAT('site-', sl.id::text) AS id,
                    {_legacy_site_label_expr("COALESCE(sl.site_code, 'shopee_tw')")} AS site,
                    LOWER(COALESCE(sl.site_code, 'shopee_tw')) AS site_code,
                    sl.shop_code,
                    COALESCE(NULLIF(sl.listing_title, ''), NULLIF(sl.original_title_snapshot, '')) AS optimized_title,
                    COALESCE(sl.publish_status, sl.status, 'draft') AS status,
                    sl.updated_at,
                    0 AS source_rank
                FROM site_listings sl
                WHERE sl.product_id = %s AND COALESCE(sl.is_deleted, 0) = 0

                UNION ALL

                SELECT
                    CONCAT('legacy-', pli.id::text) AS id,
                    'TW' AS site,
                    'TW' AS site_code,
                    NULL::text AS shop_code,
                    pli.optimized_title,
                    pli.status,
                    pli.updated_at,
                    1 AS source_rank
                FROM product_listing_info pli
                WHERE pli.alibaba_product_id = %s OR pli.product_id_new = %s
            ), deduped AS (
                SELECT DISTINCT ON (site_code, COALESCE(shop_code, ''))
                    id,
                    site,
                    site_code,
                    shop_code,
                    optimized_title,
                    status,
                    updated_at,
                    source_rank
                FROM ranked_listings
                ORDER BY site_code, COALESCE(shop_code, ''), source_rank ASC, updated_at DESC NULLS LAST
            )
            SELECT
                id,
                site,
                site_code,
                shop_code,
                optimized_title,
                status,
                updated_at
            FROM deduped
            ORDER BY updated_at DESC NULLS LAST, source_rank ASC
            LIMIT 12
            """,
            (product_id, product.get('alibaba_product_id'), product.get('product_id_new')),
        )
        site_listings = cast(List[Dict[str, Any]], list(cur.fetchall()))

        cur.execute(
            f"""
            SELECT
                {_profit_analysis_site_expr()} AS site,
                {_profit_analysis_site_code_expr()} AS site_code,
                COUNT(*) AS sku_count,
                MAX(updated_at) AS last_analysis_at
            FROM product_analysis pa
            WHERE pa.product_id = %s AND COALESCE(pa.is_deleted, 0) = 0
            GROUP BY {_profit_analysis_site_expr()}, {_profit_analysis_site_code_expr()}
            ORDER BY MAX(updated_at) DESC NULLS LAST
            LIMIT 1
            """,
            (product_id,),
        )
        profit_summary = cast(Dict[str, Any] | None, cur.fetchone())

    weights: List[float] = [float(sku['package_weight']) for sku in skus if isinstance(sku.get('package_weight'), (int, float))]
    media_assets = _fetch_media_assets_for_product(product_id)
    if not media_assets['main_media_assets'] and isinstance(product.get('main_images'), list):
        product['main_images'] = _resolve_scraped_image_urls_via_cos(product, 'main_images', cast(List[Any], product.get('main_images') or []))
    if not media_assets['sku_media_assets'] and isinstance(product.get('sku_images'), list):
        product['sku_images'] = _resolve_scraped_image_urls_via_cos(product, 'sku_images', cast(List[Any], product.get('sku_images') or []))
    product['skus'] = skus
    product['published_sites'] = [
        normalized
        for normalized in (_to_legacy_site_label(site_code) for site_code in cast(List[Any], product.get('published_sites') or []))
        if normalized
    ]
    raw_site_status = _as_string_dict(product.get('site_status'))
    if raw_site_status:
        product['site_status'] = {
            normalized: value
            for raw_site, value in raw_site_status.items()
            for normalized in [_to_legacy_site_label(raw_site)]
            if normalized
        }
    product['site_listings'] = site_listings
    product['main_media_assets'] = media_assets['main_media_assets']
    product['sku_media_assets'] = media_assets['sku_media_assets']
    product['profit_summary'] = profit_summary
    product['logistics_summary'] = {
        'total_stock': sum(int(sku.get('stock') or 0) for sku in skus),
        'weight_min': min(weights, default=None),
        'weight_max': max(weights, default=None),
    }
    product['site_summary'] = {
        'listing_count': len(site_listings),
        'published_count': len(product.get('published_sites') or []),
        'draft_count': len([listing for listing in site_listings if str(listing.get('status') or '').lower() != 'published']),
    }
    return product


def fetch_product_debug_snapshot(product_id_new: str) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                p.id,
                p.alibaba_product_id,
                p.product_id_new,
                p.created_at,
                p.updated_at,
                p.title,
                p.optimized_title,
                p.description,
                p.optimized_description,
                p.category,
                p.brand,
                p.origin,
                p.status::text AS status,
                COALESCE(p.main_images, '[]'::jsonb) AS main_images,
                COALESCE(p.skus, '[]'::jsonb) AS skus,
                COALESCE(p.logistics, '{}'::jsonb) AS logistics
            FROM products p
            WHERE p.product_id_new = %s AND COALESCE(p.is_deleted, 0) = 0
            ORDER BY p.updated_at DESC NULLS LAST, p.id DESC
            LIMIT 1
            """,
            (product_id_new,),
        )
        product = cast(Dict[str, Any] | None, cur.fetchone())
        if not product:
            return None

        cur.execute(
            """
            SELECT
                s.id,
                s.sku_name,
                s.shopee_sku_name,
                s.sku_code,
                s.price,
                s.stock,
                s.currency,
                s.package_weight,
                s.package_length,
                s.package_width,
                s.package_height,
                s.image_url
            FROM product_skus s
            WHERE s.product_id = %s AND COALESCE(s.is_deleted, 0) = 0
            ORDER BY s.id ASC
            """,
            (product['id'],),
        )
        db_skus = cast(List[Dict[str, Any]], list(cur.fetchall()))
        source_skus = product.get('skus')
        if not isinstance(source_skus, list) or not source_skus:
            source_skus = db_skus
        product['skus'] = source_skus
        product['db_skus'] = db_skus
        product['preview_image_url'] = _resolve_product_preview_image_url(product)
        return product


def fetch_system_configs(
    page: int = 1,
    page_size: int = 100,
    category: str | None = None,
    environment: str | None = None,
    keyword: str | None = None,
    verify_status: str | None = None,
    is_active: bool | None = None,
) -> Dict[str, Any]:
    items = _build_system_configs()

    if category:
        items = [item for item in items if item['category'] == category]
    if environment:
        items = [item for item in items if item['environment'] == environment]
    if keyword:
        needle = keyword.lower()
        items = [item for item in items if needle in item['config_key'].lower() or needle in item['config_name'].lower()]
    if verify_status:
        items = [item for item in items if item.get('last_verify_status') == verify_status]
    if is_active is not None:
        items = [item for item in items if item.get('is_active') == is_active]

    return _paginate_items(items, page, page_size)


def fetch_system_config(config_key: str, environment: str = 'prod') -> Dict[str, Any] | None:
    for item in _build_system_configs():
        if item['config_key'] == config_key and item['environment'] == environment:
            return item
    return None


def fetch_system_config_summary() -> Dict[str, Any]:
    items = _build_system_configs()
    categories: Dict[str, Dict[str, Any]] = {}
    failed_configs = 0
    expiring_configs = 0

    for item in items:
        category = item['category']
        if category not in categories:
            categories[category] = {
                'category': category,
                'total': 0,
                'failed': 0,
                'expiring': 0,
                'last_updated_at': item.get('updated_at'),
            }
        categories[category]['total'] += 1
        if item.get('last_verify_status') == 'warning':
            categories[category]['failed'] += 1
            failed_configs += 1
        if item.get('expires_at'):
            categories[category]['expiring'] += 1
            expiring_configs += 1

    return {
        'total_configs': len(items),
        'failed_configs': failed_configs,
        'expiring_configs': expiring_configs,
        'categories': list(categories.values()),
    }


def update_product_fields(product_id: int, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    allowed_fields = ['optimized_title', 'optimized_description', 'category', 'brand', 'status']
    updates = {key: value for key, value in payload.items() if key in allowed_fields}
    if not updates:
        raise ValueError('no product fields to update')

    set_clauses: List[str] = []
    params: List[Any] = []
    for key, value in updates.items():
        set_clauses.append(f'{key} = %s')
        params.append(value)
    params.append(product_id)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, alibaba_product_id, product_id_new FROM products WHERE id = %s AND COALESCE(is_deleted, 0) = 0", (product_id,))
        product = cast(Dict[str, Any] | None, cur.fetchone())
        if not product:
            return None

        cur.execute(
            f"UPDATE products SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            tuple(params),
        )

        listing_updates: List[str] = []
        listing_params: List[Any] = []
        if 'optimized_title' in updates:
            listing_updates.append('optimized_title = %s')
            listing_params.append(updates['optimized_title'])
        if 'optimized_description' in updates:
            listing_updates.append('optimized_description = %s')
            listing_params.append(updates['optimized_description'])

        if listing_updates:
            listing_params.extend([product.get('alibaba_product_id'), product.get('product_id_new')])
            cur.execute(
                f"""
                UPDATE product_listing_info
                SET {', '.join(listing_updates)}, updated_at = CURRENT_TIMESTAMP
                WHERE alibaba_product_id = %s OR product_id_new = %s
                """,
                tuple(listing_params),
            )

        conn.commit()

    return fetch_product(product_id)


def update_product_sku_fields(product_id: int, sku_id: int, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    allowed_fields = ['shopee_sku_name']
    updates = {key: value for key, value in payload.items() if key in allowed_fields}
    if not updates:
        raise ValueError('no sku fields to update')

    set_clauses: List[str] = []
    params: List[Any] = []
    for key, value in updates.items():
        set_clauses.append(f'{key} = %s')
        params.append(value)
    params.extend([product_id, sku_id])

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM products WHERE id = %s AND COALESCE(is_deleted, 0) = 0",
            (product_id,),
        )
        product = cast(Dict[str, Any] | None, cur.fetchone())
        if not product:
            return None

        cur.execute(
            "SELECT id FROM product_skus WHERE product_id = %s AND id = %s AND COALESCE(is_deleted, 0) = 0",
            (product_id, sku_id),
        )
        sku = cast(Dict[str, Any] | None, cur.fetchone())
        if not sku:
            return None

        cur.execute(
            f"UPDATE product_skus SET {', '.join(set_clauses)} WHERE product_id = %s AND id = %s",
            tuple(params),
        )
        conn.commit()

    return fetch_product(product_id)


def upsert_system_config_record(config_key: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    environment = str(payload.get('environment') or 'prod')
    base_item = fetch_system_config(config_key, environment=environment)
    if not base_item:
        return None

    value = cast(str | None, payload.get('value'))
    description = cast(str | None, payload.get('description'))
    change_reason = cast(str | None, payload.get('change_reason'))
    operator_name = cast(str | None, payload.get('operator_name'))
    verify_after_save = bool(payload.get('verify_after_save', True))

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, value_encrypted, value_masked, description FROM system_configs WHERE config_key = %s AND environment = %s",
            (config_key, environment),
        )
        existing = cast(Dict[str, Any] | None, cur.fetchone())

        previous_encrypted = cast(str | None, (existing or {}).get('value_encrypted'))
        previous_masked = cast(str | None, (existing or {}).get('value_masked')) or cast(str | None, base_item.get('value_masked'))
        effective_plaintext = value if value is not None else _decrypt_config_value(previous_encrypted)
        encrypted_value = _encrypt_config_value(effective_plaintext) if effective_plaintext is not None else previous_encrypted
        masked_value = payload.get('value_masked') or (_mask_value(effective_plaintext) if effective_plaintext is not None else previous_masked)
        validation = _validate_config_value(config_key, effective_plaintext, base_item) if verify_after_save else {'status': 'warning', 'message': '已跳过自动验证'}

        cur.execute(
            """
            INSERT INTO system_configs (
                config_key,
                config_name,
                category,
                environment,
                value_type,
                secret_level,
                value_encrypted,
                value_masked,
                description,
                schema_json,
                dependency_json,
                is_required,
                is_active,
                last_verified_at,
                last_verify_status,
                last_verify_message,
                updated_at,
                updated_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (config_key, environment)
            DO UPDATE SET
                config_name = EXCLUDED.config_name,
                category = EXCLUDED.category,
                value_type = EXCLUDED.value_type,
                secret_level = EXCLUDED.secret_level,
                value_encrypted = COALESCE(EXCLUDED.value_encrypted, system_configs.value_encrypted),
                value_masked = EXCLUDED.value_masked,
                description = COALESCE(EXCLUDED.description, system_configs.description),
                schema_json = EXCLUDED.schema_json,
                dependency_json = EXCLUDED.dependency_json,
                is_required = EXCLUDED.is_required,
                is_active = EXCLUDED.is_active,
                last_verified_at = EXCLUDED.last_verified_at,
                last_verify_status = EXCLUDED.last_verify_status,
                last_verify_message = EXCLUDED.last_verify_message,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = EXCLUDED.updated_by
            RETURNING id
            """,
            (
                config_key,
                base_item.get('config_name'),
                base_item.get('category'),
                environment,
                base_item.get('value_type'),
                base_item.get('secret_level'),
                encrypted_value,
                masked_value,
                description,
                Json(base_item.get('schema_json') or {}),
                Json(base_item.get('dependency_json') or {}),
                base_item.get('is_required', True),
                base_item.get('is_active', True),
                validation['status'],
                validation['message'],
                operator_name,
            ),
        )
        row = cast(Dict[str, Any], cur.fetchone() or {})
        config_id = int(row['id'])

        cur.execute(
            """
            INSERT INTO config_change_logs (
                config_id,
                action_type,
                old_value_encrypted,
                old_value_masked,
                new_value_encrypted,
                new_value_masked,
                change_reason,
                verify_status,
                verify_message,
                operator_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                config_id,
                'update',
                previous_encrypted,
                previous_masked,
                encrypted_value,
                masked_value,
                change_reason,
                validation['status'],
                validation['message'],
                operator_name,
            ),
        )
        conn.commit()

    return fetch_system_config(config_key, environment=environment)


def rollback_system_config_record(config_key: str, environment: str, log_id: int, operator_name: str) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    base_item = fetch_system_config(config_key, environment=environment)
    if not base_item:
        return None

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, value_encrypted, value_masked FROM system_configs WHERE config_key = %s AND environment = %s",
            (config_key, environment),
        )
        current = cast(Dict[str, Any] | None, cur.fetchone())
        if not current:
            return None

        cur.execute(
            """
            SELECT id, old_value_encrypted, old_value_masked, new_value_encrypted, new_value_masked
            FROM config_change_logs
            WHERE id = %s AND config_id = %s
            """,
            (log_id, current['id']),
        )
        log_row = cast(Dict[str, Any] | None, cur.fetchone())
        if not log_row:
            return None

        rollback_encrypted = cast(str | None, log_row.get('old_value_encrypted'))
        rollback_masked = cast(str | None, log_row.get('old_value_masked'))
        rollback_value = _decrypt_config_value(rollback_encrypted) if rollback_encrypted else None
        validation = _validate_config_value(config_key, rollback_value, base_item)

        cur.execute(
            """
            UPDATE system_configs
            SET value_encrypted = %s,
                value_masked = %s,
                last_verified_at = CURRENT_TIMESTAMP,
                last_verify_status = %s,
                last_verify_message = %s,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = %s
            WHERE id = %s
            """,
            (
                rollback_encrypted,
                rollback_masked,
                validation['status'],
                f"回滚到变更#{log_id}: {validation['message']}",
                operator_name,
                current['id'],
            ),
        )

        cur.execute(
            """
            INSERT INTO config_change_logs (
                config_id,
                action_type,
                old_value_encrypted,
                old_value_masked,
                new_value_encrypted,
                new_value_masked,
                change_reason,
                verify_status,
                verify_message,
                operator_name
            ) VALUES (%s, 'rollback', %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                current['id'],
                current.get('value_encrypted'),
                current.get('value_masked'),
                rollback_encrypted,
                rollback_masked,
                f'回滚到历史记录#{log_id}',
                validation['status'],
                validation['message'],
                operator_name,
            ),
        )
        conn.commit()

    return fetch_system_config(config_key, environment=environment)


def _coerce_json_field(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _prepare_update_statement(payload: Dict[str, Any], allowed_fields: List[str], json_fields: set[str]) -> tuple[list[str], list[Any]]:
    set_clauses: list[str] = []
    params: list[Any] = []
    for field in allowed_fields:
        if field not in payload:
            continue
        value = payload.get(field)
        if field in json_fields and value is not None:
            value = _coerce_json_field(value)
            params.append(Json(value))
        else:
            params.append(value)
        set_clauses.append(f'{field} = %s')
    return set_clauses, params


def fetch_market_configs(
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
) -> Dict[str, Any]:
    filters = ['1=1']
    params: List[Any] = []
    if keyword:
        needle = f'%{keyword.strip()}%'
        filters.append('(market_code ILIKE %s OR COALESCE(config_name, \'\') ILIKE %s OR site_code ILIKE %s)')
        params.extend([needle, needle, needle])
    if site_code:
        filters.append('site_code = %s')
        params.append(site_code)
    if is_active is not None:
        filters.append('is_active = %s')
        params.append(is_active)

    where_clause = ' AND '.join(filters)
    base_sql = f'''
        SELECT
            id,
            market_code,
            config_name,
            channel_code,
            site_code,
            default_currency,
            source_language,
            listing_language,
            default_shipping_profile_code,
            default_content_policy_code,
            commission_free_days,
            allow_publish,
            allow_profit_analysis,
            allow_listing_optimization,
            is_active,
            updated_at
        FROM public.market_configs
        WHERE {where_clause}
        ORDER BY is_active DESC, updated_at DESC NULLS LAST, market_code ASC
    '''
    count_sql = f'SELECT COUNT(*) AS total FROM public.market_configs WHERE {where_clause}'
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_market_config(market_code: str) -> Dict[str, Any] | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM public.market_configs WHERE market_code = %s', (market_code,))
        return cast(Dict[str, Any] | None, cur.fetchone())


def upsert_market_config_record(market_code: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    allowed_fields = [
        'config_name', 'channel_code', 'site_code', 'default_currency', 'source_language', 'listing_language',
        'default_shipping_profile_code', 'default_content_policy_code', 'default_fee_profile_code',
        'default_erp_profile_code', 'default_category_profile_code', 'default_price_policy_code',
        'commission_free_days', 'allow_publish', 'allow_profit_analysis', 'allow_listing_optimization', 'is_active', 'metadata',
        'effective_from', 'effective_to',
    ]
    set_clauses, params = _prepare_update_statement(payload, allowed_fields, {'metadata'})
    if not set_clauses:
        return fetch_market_config(market_code)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM public.market_configs WHERE market_code = %s', (market_code,))
        if not cur.fetchone():
            return None
        params.extend([market_code])
        cur.execute(
            f"UPDATE public.market_configs SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE market_code = %s",
            tuple(params),
        )
        conn.commit()
    return fetch_market_config(market_code)


def fetch_shipping_profiles(
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
) -> Dict[str, Any]:
    filters = ['1=1']
    params: List[Any] = []
    if keyword:
        needle = f'%{keyword.strip()}%'
        filters.append('(shipping_profile_code ILIKE %s OR COALESCE(profile_name, \'\') ILIKE %s OR site_code ILIKE %s)')
        params.extend([needle, needle, needle])
    if site_code:
        filters.append('site_code = %s')
        params.append(site_code)
    if is_active is not None:
        filters.append('is_active = %s')
        params.append(is_active)

    where_clause = ' AND '.join(filters)
    base_sql = f'''
        SELECT
            id,
            shipping_profile_code,
            profile_name,
            market_code,
            site_code,
            channel_name,
            currency,
            chargeable_weight_mode,
            first_weight_g,
            first_weight_fee,
            continue_weight_g,
            continue_weight_fee,
            is_default,
            is_active,
            updated_at
        FROM public.shipping_profiles
        WHERE {where_clause}
        ORDER BY is_default DESC, is_active DESC, updated_at DESC NULLS LAST, shipping_profile_code ASC
    '''
    count_sql = f'SELECT COUNT(*) AS total FROM public.shipping_profiles WHERE {where_clause}'
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_shipping_profile(shipping_profile_code: str) -> Dict[str, Any] | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM public.shipping_profiles WHERE shipping_profile_code = %s', (shipping_profile_code,))
        return cast(Dict[str, Any] | None, cur.fetchone())


def upsert_shipping_profile_record(shipping_profile_code: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    allowed_fields = [
        'profile_name', 'market_code', 'site_code', 'channel_name', 'currency', 'chargeable_weight_mode',
        'weight_rounding_mode', 'weight_rounding_base_g', 'volumetric_divisor', 'first_weight_g',
        'first_weight_fee', 'continue_weight_g', 'continue_weight_fee', 'max_weight_g',
        'shipping_subsidy_rule_type', 'subsidy_rules_json', 'hidden_shipping_formula',
        'hidden_shipping_continue_fee', 'platform_shipping_fee_rate', 'platform_shipping_fee_cap',
        'is_default', 'is_active', 'metadata',
    ]
    set_clauses, params = _prepare_update_statement(payload, allowed_fields, {'subsidy_rules_json', 'metadata'})
    if not set_clauses:
        return fetch_shipping_profile(shipping_profile_code)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM public.shipping_profiles WHERE shipping_profile_code = %s', (shipping_profile_code,))
        if not cur.fetchone():
            return None
        params.extend([shipping_profile_code])
        cur.execute(
            f"UPDATE public.shipping_profiles SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE shipping_profile_code = %s",
            tuple(params),
        )
        conn.commit()
    return fetch_shipping_profile(shipping_profile_code)


def fetch_content_policies(
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
) -> Dict[str, Any]:
    filters = ['1=1']
    params: List[Any] = []
    if keyword:
        needle = f'%{keyword.strip()}%'
        filters.append('(content_policy_code ILIKE %s OR COALESCE(policy_name, \'\') ILIKE %s OR site_code ILIKE %s)')
        params.extend([needle, needle, needle])
    if site_code:
        filters.append('site_code = %s')
        params.append(site_code)
    if is_active is not None:
        filters.append('is_active = %s')
        params.append(is_active)

    where_clause = ' AND '.join(filters)
    base_sql = f'''
        SELECT
            id,
            content_policy_code,
            policy_name,
            market_code,
            site_code,
            prompt_profile_code,
            source_language,
            listing_language,
            translation_mode,
            title_min_length,
            title_max_length,
            description_min_length,
            description_max_length,
            is_default,
            is_active,
            updated_at
        FROM public.content_policies
        WHERE {where_clause}
        ORDER BY is_default DESC, is_active DESC, updated_at DESC NULLS LAST, content_policy_code ASC
    '''
    count_sql = f'SELECT COUNT(*) AS total FROM public.content_policies WHERE {where_clause}'
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_content_policy(content_policy_code: str) -> Dict[str, Any] | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM public.content_policies WHERE content_policy_code = %s', (content_policy_code,))
        return cast(Dict[str, Any] | None, cur.fetchone())


def upsert_content_policy_record(content_policy_code: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    allowed_fields = [
        'policy_name', 'market_code', 'site_code', 'prompt_profile_code', 'source_language', 'listing_language', 'translation_mode',
        'title_min_length', 'title_max_length', 'description_min_length', 'description_max_length',
        'forbidden_terms_json', 'required_sections_json', 'term_mapping_json', 'validation_rule_set',
        'prompt_base_template', 'prompt_title_variant', 'prompt_desc_variant', 'fallback_to_source_title',
        'fallback_to_source_description', 'is_default', 'is_active', 'metadata',
    ]
    set_clauses, params = _prepare_update_statement(
        payload,
        allowed_fields,
        {'forbidden_terms_json', 'required_sections_json', 'term_mapping_json', 'validation_rule_set', 'metadata'},
    )
    if not set_clauses:
        return fetch_content_policy(content_policy_code)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM public.content_policies WHERE content_policy_code = %s', (content_policy_code,))
        if not cur.fetchone():
            return None
        params.extend([content_policy_code])
        cur.execute(
            f"UPDATE public.content_policies SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE content_policy_code = %s",
            tuple(params),
        )
        conn.commit()
    return fetch_content_policy(content_policy_code)


def fetch_prompt_profiles(
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
) -> Dict[str, Any]:
    _ensure_foundation_tables()
    filters = ['1=1']
    params: List[Any] = []
    if keyword:
        needle = f'%{keyword.strip()}%'
        filters.append('(prompt_profile_code ILIKE %s OR COALESCE(profile_name, \'\') ILIKE %s OR site_code ILIKE %s)')
        params.extend([needle, needle, needle])
    if site_code:
        filters.append("(site_code = %s OR COALESCE(metadata ->> 'is_global_template', 'false') = 'true')")
        params.append(site_code)
    if is_active is not None:
        filters.append('is_active = %s')
        params.append(is_active)

    where_clause = ' AND '.join(filters)
    base_sql = f'''
        SELECT
            id,
            prompt_profile_code,
            profile_name,
            market_code,
            site_code,
            is_default,
            is_active,
            updated_at
        FROM public.prompt_profiles
        WHERE {where_clause}
        ORDER BY is_default DESC, is_active DESC, updated_at DESC NULLS LAST, prompt_profile_code ASC
    '''
    count_sql = f'SELECT COUNT(*) AS total FROM public.prompt_profiles WHERE {where_clause}'
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_prompt_profile(prompt_profile_code: str) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM public.prompt_profiles WHERE prompt_profile_code = %s', (prompt_profile_code,))
        return cast(Dict[str, Any] | None, cur.fetchone())


def upsert_prompt_profile_record(prompt_profile_code: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    allowed_fields = [
        'profile_name', 'market_code', 'site_code', 'title_template', 'description_template', 'sku_name_template',
        'template_variables_json', 'notes', 'is_default', 'is_active', 'metadata',
    ]
    set_clauses, params = _prepare_update_statement(payload, allowed_fields, {'template_variables_json', 'metadata'})
    if not set_clauses:
        return fetch_prompt_profile(prompt_profile_code)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM public.prompt_profiles WHERE prompt_profile_code = %s', (prompt_profile_code,))
        if cur.fetchone():
            params.extend([prompt_profile_code])
            cur.execute(
                f"UPDATE public.prompt_profiles SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE prompt_profile_code = %s",
                tuple(params),
            )
        else:
            field_names = ['prompt_profile_code']
            field_params: list[Any] = [prompt_profile_code]
            for field in allowed_fields:
                if field not in payload:
                    continue
                value = payload.get(field)
                if field in {'template_variables_json', 'metadata'} and value is not None:
                    value = Json(_coerce_json_field(value))
                field_names.append(field)
                field_params.append(value)
            placeholders = ', '.join(['%s'] * len(field_names))
            cur.execute(
                f"INSERT INTO public.prompt_profiles ({', '.join(field_names)}) VALUES ({placeholders})",
                tuple(field_params),
            )
        conn.commit()
    return fetch_prompt_profile(prompt_profile_code)


def fetch_fee_profiles(
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    is_active: bool | None = None,
) -> Dict[str, Any]:
    _ensure_foundation_tables()
    filters = ['1=1']
    params: List[Any] = []
    if keyword:
        needle = f'%{keyword.strip()}%'
        filters.append('(fee_profile_code ILIKE %s OR COALESCE(profile_name, \'\') ILIKE %s OR site_code ILIKE %s)')
        params.extend([needle, needle, needle])
    if site_code:
        filters.append('site_code = %s')
        params.append(site_code)
    if is_active is not None:
        filters.append('is_active = %s')
        params.append(is_active)

    where_clause = ' AND '.join(filters)
    base_sql = f'''
        SELECT
            id,
            fee_profile_code,
            profile_name,
            market_code,
            site_code,
            currency,
            commission_rate,
            transaction_fee_rate,
            pre_sale_service_rate,
            agent_fee_cny,
            commission_free_days,
            is_default,
            is_active,
            updated_at
        FROM public.fee_profiles
        WHERE {where_clause}
        ORDER BY is_default DESC, is_active DESC, updated_at DESC NULLS LAST, fee_profile_code ASC
    '''
    count_sql = f'SELECT COUNT(*) AS total FROM public.fee_profiles WHERE {where_clause}'
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_fee_profile(fee_profile_code: str) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM public.fee_profiles WHERE fee_profile_code = %s', (fee_profile_code,))
        return cast(Dict[str, Any] | None, cur.fetchone())


def upsert_fee_profile_record(fee_profile_code: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    allowed_fields = [
        'profile_name', 'market_code', 'site_code', 'currency', 'commission_rate', 'transaction_fee_rate',
        'pre_sale_service_rate', 'tax_rate', 'agent_fee_cny', 'commission_free_days',
        'buyer_shipping_ordinary', 'buyer_shipping_discount', 'buyer_shipping_free',
        'hidden_price_mode', 'hidden_price_value', 'is_default', 'is_active', 'metadata',
    ]
    set_clauses, params = _prepare_update_statement(payload, allowed_fields, {'metadata'})
    if not set_clauses:
        return fetch_fee_profile(fee_profile_code)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM public.fee_profiles WHERE fee_profile_code = %s', (fee_profile_code,))
        if cur.fetchone():
            params.extend([fee_profile_code])
            cur.execute(
                f"UPDATE public.fee_profiles SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE fee_profile_code = %s",
                tuple(params),
            )
        else:
            field_names = ['fee_profile_code']
            field_params: list[Any] = [fee_profile_code]
            for field in allowed_fields:
                if field not in payload:
                    continue
                field_names.append(field)
                field_params.append(payload.get(field))
            placeholders = ', '.join(['%s'] * len(field_names))
            cur.execute(
                f"INSERT INTO public.fee_profiles ({', '.join(field_names)}) VALUES ({placeholders})",
                tuple(field_params),
            )
        conn.commit()
    return fetch_fee_profile(fee_profile_code)


def fetch_site_listings(
    page: int = 1,
    page_size: int = 100,
    keyword: str | None = None,
    site_code: str | None = None,
    publish_status: str | None = None,
    sync_status: str | None = None,
) -> Dict[str, Any]:
    filters = ['COALESCE(sl.is_deleted, 0) = 0']
    params: List[Any] = []
    if keyword:
        needle = f'%{keyword.strip()}%'
        filters.append('(' 
                       'COALESCE(sl.alibaba_product_id, \'\') ILIKE %s '
                       'OR COALESCE(sl.product_id_new, \'\') ILIKE %s '
                       'OR COALESCE(sl.listing_title, \'\') ILIKE %s '
                       'OR COALESCE(p.title, \'\') ILIKE %s)')
        params.extend([needle, needle, needle, needle])
    if site_code:
        filters.append('sl.site_code = %s')
        params.append(site_code)
    if publish_status:
        filters.append('sl.publish_status = %s')
        params.append(publish_status)
    if sync_status:
        filters.append('sl.sync_status = %s')
        params.append(sync_status)

    where_clause = ' AND '.join(filters)
    base_sql = f'''
        SELECT
            sl.id,
            sl.market_code,
            sl.site_code,
            sl.shop_code,
            sl.alibaba_product_id,
            sl.product_id_new,
            COALESCE(NULLIF(sl.listing_title, ''), NULLIF(p.optimized_title, ''), NULLIF(p.title, ''), '') AS listing_title,
            sl.content_policy_code,
            sl.shipping_profile_code,
            sl.status,
            sl.publish_status,
            sl.sync_status,
            sl.currency,
            sl.estimated_profit_local,
            sl.updated_at
        FROM public.site_listings sl
        LEFT JOIN public.products p ON p.id = sl.product_id
        WHERE {where_clause}
        ORDER BY sl.updated_at DESC NULLS LAST, sl.id DESC
    '''
    count_sql = f'''
        SELECT COUNT(*) AS total
        FROM public.site_listings sl
        LEFT JOIN public.products p ON p.id = sl.product_id
        WHERE {where_clause}
    '''
    return _paginate(base_sql, count_sql, tuple(params), page, page_size)


def fetch_site_listing(site_listing_id: int) -> Dict[str, Any] | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT
                sl.*,
                p.title AS product_title,
                p.optimized_title AS product_optimized_title,
                p.optimized_description AS product_optimized_description
            FROM public.site_listings sl
            LEFT JOIN public.products p ON p.id = sl.product_id
            WHERE sl.id = %s AND COALESCE(sl.is_deleted, 0) = 0
            ''',
            (site_listing_id,),
        )
        return cast(Dict[str, Any] | None, cur.fetchone())


def create_media_upload_ticket(payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_foundation_tables()
    expires_at_ts = int(datetime.now().timestamp()) + 900
    token_payload: Dict[str, Any] = {
        'product_id': int(payload['product_id']),
        'sku_id': int(payload['sku_id']) if payload.get('sku_id') else None,
        'usage_type': str(payload['usage_type']),
        'media_type': str(payload.get('media_type') or 'image'),
        'file_name': str(payload['file_name']),
        'content_type': str(payload['content_type']),
        'size_bytes': int(payload['size_bytes']),
        'expires_at_ts': expires_at_ts,
        'nonce': uuid.uuid4().hex,
    }
    return {
        'upload_token': _serialize_media_payload(token_payload),
        'expires_at': datetime.fromtimestamp(expires_at_ts).isoformat(timespec='seconds'),
        'max_size_bytes': settings.media_upload_max_size_bytes,
    }


def store_media_asset(upload_token: str, file_bytes: bytes, operator_name: str) -> Dict[str, Any]:
    _ensure_foundation_tables()
    payload = _deserialize_media_payload(upload_token)
    product_id = int(payload['product_id'])
    sku_id = int(payload['sku_id']) if payload.get('sku_id') else None
    owner_type = 'product_sku' if payload['usage_type'] == 'sku_image' and sku_id else 'product'
    owner_id = sku_id if owner_type == 'product_sku' else product_id

    if len(file_bytes) > settings.media_upload_max_size_bytes:
        raise ValueError('file exceeds size limit')

    file_name = str(payload['file_name'])
    image_meta = _validate_and_probe_image(file_bytes)
    checksum = hashlib.sha256(file_bytes).hexdigest()
    object_key = _build_s3_object_key(product_id, str(payload['usage_type']), file_name)

    try:
        s3_client = _build_s3_client()
        s3_client.put_object(
            Bucket=settings.s3_bucket,
            Key=object_key,
            Body=file_bytes,
            ContentType=str(payload['content_type']),
        )
    except (BotoCoreError, ClientError) as exc:
        raise ValueError(f'failed to upload media to S3: {exc}') from exc

    public_url = _build_s3_asset_url(object_key)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM products WHERE id = %s AND COALESCE(is_deleted, 0) = 0", (product_id,))
        if not cur.fetchone():
            raise ValueError('product not found')
        if owner_type == 'product_sku':
            cur.execute(
                "SELECT id FROM product_skus WHERE id = %s AND product_id = %s AND COALESCE(is_deleted, 0) = 0",
                (sku_id, product_id),
            )
            if not cur.fetchone():
                raise ValueError('sku not found for product')

        cur.execute(
            """
            INSERT INTO media_assets (
                owner_type,
                owner_id,
                media_type,
                usage_type,
                source_url,
                oss_key,
                oss_url,
                file_name,
                mime_type,
                file_size_bytes,
                width_px,
                height_px,
                sort_order,
                status,
                checksum,
                uploaded_by,
                uploaded_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, owner_type, owner_id, media_type, usage_type, file_name, mime_type, file_size_bytes, width_px, height_px, sort_order, status, oss_url, uploaded_at
            """,
            (
                owner_type,
                owner_id,
                payload['media_type'],
                payload['usage_type'],
                None,
                object_key,
                public_url,
                file_name,
                image_meta['mime_type'],
                len(file_bytes),
                image_meta['width_px'],
                image_meta['height_px'],
                0,
                checksum,
                operator_name,
            ),
        )
        asset = cast(Dict[str, Any], cur.fetchone() or {})
        asset_id = int(asset['id'])

        _sync_product_media_columns(cur, product_id)
        if sku_id:
            cur.execute(
                "UPDATE product_skus SET image_url = %s WHERE id = %s",
                (_media_content_path(asset_id), sku_id),
            )

        conn.commit()

    asset['asset_url'] = _media_content_path(asset_id)
    asset['sku_id'] = sku_id
    return asset


def sort_media_assets(product_id: int, usage_type: str, asset_ids: List[int]) -> Dict[str, Any] | None:
    _ensure_foundation_tables()
    owner_type = 'product' if usage_type == 'main_image' else 'product_sku'

    with get_connection() as conn:
        cur = conn.cursor()
        if owner_type == 'product':
            cur.execute(
                "SELECT id FROM media_assets WHERE owner_type = 'product' AND owner_id = %s AND COALESCE(is_deleted, 0) = 0",
                (product_id,),
            )
        else:
            cur.execute(
                """
                SELECT m.id
                FROM media_assets m
                INNER JOIN product_skus s ON s.id = m.owner_id
                WHERE m.owner_type = 'product_sku'
                  AND s.product_id = %s
                  AND COALESCE(m.is_deleted, 0) = 0
                """,
                (product_id,),
            )
        existing_ids = {int(row['id']) for row in cast(List[Dict[str, Any]], list(cur.fetchall()))}
        if set(asset_ids) != existing_ids:
            raise ValueError('asset order payload does not match current assets')

        for index, asset_id in enumerate(asset_ids):
            cur.execute(
                "UPDATE media_assets SET sort_order = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (index, asset_id),
            )

        _sync_product_media_columns(cur, product_id)
        conn.commit()

    return fetch_product(product_id)


def delete_media_asset(product_id: int, asset_id: int) -> Dict[str, Any] | None:
    _ensure_foundation_tables()

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.id, m.owner_type, m.owner_id, m.oss_key
            FROM media_assets m
            LEFT JOIN product_skus s ON s.id = m.owner_id AND m.owner_type = 'product_sku'
            WHERE m.id = %s
              AND COALESCE(m.is_deleted, 0) = 0
              AND (
                (m.owner_type = 'product' AND m.owner_id = %s)
                OR (m.owner_type = 'product_sku' AND s.product_id = %s)
              )
            """,
            (asset_id, product_id, product_id),
        )
        asset = cast(Dict[str, Any] | None, cur.fetchone())
        if not asset:
            return None

        if asset.get('oss_key'):
            try:
                _build_s3_client().delete_object(Bucket=settings.s3_bucket, Key=str(asset['oss_key']))
            except (BotoCoreError, ClientError) as exc:
                raise ValueError(f'failed to delete media from S3: {exc}') from exc

        cur.execute(
            "UPDATE media_assets SET is_deleted = 1, status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (asset_id,),
        )
        _sync_product_media_columns(cur, product_id)

        if asset.get('owner_type') == 'product_sku':
            cur.execute(
                "UPDATE product_skus SET image_url = NULL WHERE id = %s",
                (asset.get('owner_id'),),
            )

        conn.commit()

    return fetch_product(product_id)


def get_media_asset_download_url(asset_id: int) -> str | None:
    _ensure_foundation_tables()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT oss_key, oss_url FROM media_assets WHERE id = %s AND COALESCE(is_deleted, 0) = 0",
            (asset_id,),
        )
        row = cast(Dict[str, Any] | None, cur.fetchone())
    if not row:
        return None
    if row.get('oss_url'):
        return str(row['oss_url'])
    if not row.get('oss_key'):
        return None
    try:
        return cast(str, _build_s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.s3_bucket, 'Key': str(row['oss_key'])},
            ExpiresIn=900,
        ))
    except (BotoCoreError, ClientError) as exc:
        raise ValueError(f'failed to generate media URL: {exc}') from exc


def fetch_agent_metrics(agent_id: int, window: str = '24h') -> Dict[str, Any]:
    if agent_id != ECOMMERCE_SERVICE_ID:
        return {
            'task_success_rate': None,
            'task_failure_count': 0,
            'avg_duration_ms': 0,
            'heartbeat_warning_count': 0,
            'heartbeat_critical_count': 0,
            'manual_queue_count': 0,
            'pending_queue_count': 0,
            'processing_queue_count': 0,
            'fix_task_priority_distribution': {},
            'stage_distribution': {},
            'stage_status_distribution': {},
            'retrospective_queue_count': 0,
            'blocked_stage_count': 0,
            'metric_timestamp': None,
            'metric_window': window,
        }

    interval_map = {
        '1h': '1 hour',
        '24h': '24 hours',
        '7d': '7 days',
    }
    interval = interval_map.get(window, '24 hours')

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            WITH log_stats AS (
                SELECT
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(run_status, '')) = 'success') AS success_count,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(run_status, '')) = 'failed') AS failure_count,
                    AVG(duration_ms) FILTER (WHERE duration_ms IS NOT NULL) AS avg_duration_ms
                FROM main_logs
                WHERE created_at > NOW() - INTERVAL '{interval}'
            ),
            heartbeat_stats AS (
                SELECT
                    COUNT(*) FILTER (WHERE heartbeat_status = 'warning') AS heartbeat_warning_count,
                    COUNT(*) FILTER (WHERE heartbeat_status = 'critical') AS heartbeat_critical_count
                FROM heartbeat_events
                WHERE report_time > NOW() - INTERVAL '{interval}'
            ),
            task_stats AS (
                SELECT
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(exec_state, '')) = 'requires_manual') AS manual_queue_count,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(exec_state, '')) IN ('new', 'error_fix_pending', 'normal_crash')) AS pending_queue_count,
                    COUNT(*) FILTER (WHERE LOWER(COALESCE(exec_state, '')) = 'processing') AS processing_queue_count
                FROM tasks
            ),
            fix_distribution AS (
                SELECT COALESCE(jsonb_object_agg(priority, cnt), '{{}}'::jsonb) AS distribution
                FROM (
                    SELECT priority, COUNT(*) AS cnt
                    FROM tasks
                    WHERE task_type = '修复'
                    GROUP BY priority
                ) d
            )
            SELECT
                CASE
                    WHEN COALESCE(log_stats.success_count, 0) + COALESCE(log_stats.failure_count, 0) = 0 THEN NULL
                    ELSE ROUND(log_stats.success_count::numeric /
                               NULLIF(log_stats.success_count + log_stats.failure_count, 0), 4)
                END AS task_success_rate,
                COALESCE(log_stats.failure_count, 0) AS task_failure_count,
                ROUND(COALESCE(log_stats.avg_duration_ms, 0)::numeric, 2) AS avg_duration_ms,
                COALESCE(heartbeat_stats.heartbeat_warning_count, 0) AS heartbeat_warning_count,
                COALESCE(heartbeat_stats.heartbeat_critical_count, 0) AS heartbeat_critical_count,
                COALESCE(task_stats.manual_queue_count, 0) AS manual_queue_count,
                COALESCE(task_stats.pending_queue_count, 0) AS pending_queue_count,
                COALESCE(task_stats.processing_queue_count, 0) AS processing_queue_count,
                fix_distribution.distribution AS fix_task_priority_distribution,
                %s AS metric_window
            FROM log_stats, heartbeat_stats, task_stats, fix_distribution
            """,
            (window,),
        )
        metrics = cast(Dict[str, Any], cur.fetchone() or {})
        lifecycle_metrics = _fetch_task_lifecycle_metrics(cur)
        metrics.update(lifecycle_metrics)
        stage_distribution = cast(Dict[str, int], metrics.get('stage_distribution') or {})
        stage_status_distribution = cast(Dict[str, int], metrics.get('stage_status_distribution') or {})
        metrics['retrospective_queue_count'] = int(stage_distribution.get('retrospective', 0))
        metrics['blocked_stage_count'] = int(stage_status_distribution.get('blocked', 0))
        return metrics
