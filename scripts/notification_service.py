#!/usr/bin/env python3
"""统一的飞书通知与文档写入服务。"""
import json
import os
import urllib.request
import urllib.error
import uuid
from functools import lru_cache
from pathlib import Path

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
CONFIG_ENV_PATH = WORKSPACE / 'config' / 'config.env'


@lru_cache(maxsize=1)
def _load_config_env() -> dict:
    config = {}
    if not CONFIG_ENV_PATH.exists():
        return config

    for line in CONFIG_ENV_PATH.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        config[key.strip()] = value.strip()
    return config


def get_feishu_webhook_url(explicit_webhook: str | None = None) -> str:
    """获取飞书 webhook，优先显式参数，其次环境变量，再次配置文件。"""
    if explicit_webhook:
        return explicit_webhook

    env_webhook = os.environ.get('FEISHU_WEBHOOK_URL')
    if env_webhook:
        return env_webhook

    return _load_config_env().get('FEISHU_WEBHOOK_URL', '')


def get_feishu_app_id() -> str:
    return os.environ.get('FEISHU_APP_ID') or _load_config_env().get('FEISHU_APP_ID', '')


def get_feishu_app_secret() -> str:
    return os.environ.get('FEISHU_APP_SECRET') or _load_config_env().get('FEISHU_APP_SECRET', '')


def _request_json(url: str, method: str = 'GET', payload: dict | None = None, headers: dict | None = None, timeout: int = 30) -> dict:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        request_headers.setdefault('Content-Type', 'application/json; charset=utf-8')

    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'HTTP {exc.code}: {body or exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


@lru_cache(maxsize=1)
def get_feishu_tenant_access_token() -> str:
    app_id = get_feishu_app_id()
    app_secret = get_feishu_app_secret()
    if not app_id or not app_secret:
        raise RuntimeError('未配置 FEISHU_APP_ID / FEISHU_APP_SECRET')

    response = _request_json(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        method='POST',
        payload={'app_id': app_id, 'app_secret': app_secret},
        timeout=15,
    )
    token = response.get('tenant_access_token', '')
    if not token:
        raise RuntimeError(f'获取 tenant_access_token 失败: {response}')
    return token


def get_docx_url(document_id: str) -> str:
    return f'https://pcn0wtpnjfsd.feishu.cn/docx/{document_id}'


def _text_block(content: str) -> dict:
    return {
        'block_type': 2,
        'text': {
            'elements': [
                {
                    'text_run': {
                        'content': content,
                    }
                }
            ],
            'style': {},
        },
    }


def _content_to_text_blocks(content: str, max_line_length: int = 1500) -> list[dict]:
    blocks = []
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        for start in range(0, len(line), max_line_length):
            chunk = line[start:start + max_line_length]
            blocks.append(_text_block(chunk))
    return blocks


def append_text_to_docx(document_id: str, content: str, timeout: int = 30) -> dict:
    blocks = _content_to_text_blocks(content)
    if not blocks:
        return {'success': True, 'document_id': document_id, 'block_count': 0, 'url': get_docx_url(document_id)}

    token = get_feishu_tenant_access_token()
    headers = {'Authorization': f'Bearer {token}'}
    total_created = 0

    for index in range(0, len(blocks), 50):
        batch = blocks[index:index + 50]
        response = _request_json(
            f'https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children?document_revision_id=-1&client_token={uuid.uuid4()}',
            method='POST',
            payload={'index': -1, 'children': batch},
            headers=headers,
            timeout=timeout,
        )
        if response.get('code') != 0:
            raise RuntimeError(f'写入飞书文档失败: {response}')
        total_created += len(batch)

    return {
        'success': True,
        'document_id': document_id,
        'block_count': total_created,
        'url': get_docx_url(document_id),
    }


def send_feishu_text(message: str, webhook_url: str | None = None, timeout: int = 10) -> bool:
    """发送飞书文本消息。"""
    webhook = get_feishu_webhook_url(webhook_url)
    if not webhook:
        print('飞书通知失败: 未配置 FEISHU_WEBHOOK_URL')
        return False

    payload = {
        'msg_type': 'text',
        'content': {'text': message},
    }

    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('code') == 0 or result.get('StatusCode') == 0
    except Exception as exc:
        print(f'飞书通知失败: {exc}')
        return False