#!/usr/bin/env python3
"""
load_env.py - 统一配置加载器

从 config/config.env 文件加载环境变量，并提供数据库连接配置。
所有脚本都应使用此模块来获取配置，避免硬编码 localhost 等参数。

用法：
    from load_env import get_db_config, get_env

    db = get_db_config()
    conn = psycopg2.connect(**db)
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 配置文件路径（相对于 workspace 根目录）
_WORKSPACE_CANDIDATES = [
    Path('/root/.openclaw/workspace-e-commerce'),
    Path(__file__).resolve().parents[1],   # scripts/ 的上级目录
]

def _find_config_env() -> Optional[Path]:
    """在可能的路径中查找 config.env"""
    for ws in _WORKSPACE_CANDIDATES:
        candidate = ws / 'config' / 'config.env'
        try:
            if candidate.exists():
                return candidate
        except (PermissionError, OSError):
            continue
    return None


def load_config_env(path: Optional[Path] = None) -> Dict[str, str]:
    """解析 config.env 文件，返回 key→value 字典（仅加载，不写入 os.environ）"""
    env_file = path or _find_config_env()
    result: Dict[str, str] = {}
    if not env_file or not env_file.exists():
        return result

    with open(env_file, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            # Strip trailing inline comment only when the value is NOT quoted
            # (quoted values may legitimately contain ' #')
            if not (len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]):
                if ' #' in value:
                    value = value[:value.index(' #')].strip()
            # Strip surrounding quotes if present
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            if key:
                result[key] = value
    return result


# 在模块加载时读取一次，供全局使用
_CONFIG: Dict[str, str] = load_config_env()


def get_env(key: str, default: str = '') -> str:
    """获取配置项。优先读取 os.environ，其次读取 config.env，最后使用 default。"""
    return os.environ.get(key) or _CONFIG.get(key, default)


def get_db_config() -> Dict[str, Any]:
    """返回 psycopg2.connect 所需的数据库连接参数字典。

    优先级：os.environ > config.env > 内置默认值
    """
    port_str = get_env('DB_PORT', '5432')
    try:
        port = int(port_str)
    except ValueError:
        port = 5432

    return {
        'host':     get_env('DB_HOST',     'localhost'),
        'port':     port,
        'database': get_env('DB_NAME',     'ecommerce_data'),
        'user':     get_env('DB_USER',     'superuser'),
        'password': get_env('DB_PASSWORD', 'Admin123!'),
    }
