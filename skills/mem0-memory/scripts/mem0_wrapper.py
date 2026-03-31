#!/usr/bin/env python3
"""
mem0-memory 技能封装
使用 Ollama qwen2.5:1.5b 作为LLM，Ollama nomic-embed-text 作为embedder
"""
import sys
import argparse
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
SCRIPT_DIR = Path(__file__).resolve().parent
SESSION_STATE_PATH = WORKSPACE / 'SESSION-STATE.md'
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(SCRIPT_DIR))

from mem0.memory.main import Memory
from mem0.configs.base import MemoryConfig, LlmConfig, EmbedderConfig, VectorStoreConfig

# Ollama 配置
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 5
OLLAMA_STARTUP_TIMEOUT = 20


class Mem0WrapperError(RuntimeError):
    """mem0 wrapper 的可读错误。"""


def _check_ollama_ready() -> bool:
    """检查 Ollama 服务是否可用。"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_TIMEOUT)
        return response.status_code == 200
    except requests.RequestException:
        return False


def _ensure_ollama_ready() -> None:
    """确保 Ollama 服务已启动，必要时自动拉起。"""
    if _check_ollama_ready():
        return

    ollama_bin = shutil.which('ollama')
    if not ollama_bin:
        raise Mem0WrapperError('未找到 ollama 可执行文件，无法启用 mem0-memory。')

    subprocess.Popen(
        [ollama_bin, 'serve'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + OLLAMA_STARTUP_TIMEOUT
    while time.time() < deadline:
        if _check_ollama_ready():
            return
        time.sleep(1)

    raise Mem0WrapperError(
        'Ollama 服务不可用，已尝试自动启动但仍未就绪。请检查 `ollama serve`。'
    )


def _get_installed_model_names() -> set[str]:
    """获取本机已安装的 Ollama 模型名。"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise Mem0WrapperError(f'无法读取 Ollama 模型列表: {exc}') from exc

    payload = response.json()
    return {model.get('name', '') for model in payload.get('models', [])}


def _pick_available_model(candidates: list[str], purpose: str) -> str:
    """从候选列表中选择本机可用模型。"""
    installed_models = _get_installed_model_names()
    for candidate in candidates:
        if candidate in installed_models:
            return candidate

    raise Mem0WrapperError(
        f'{purpose} 所需模型缺失，候选模型 {candidates} 均未安装。当前模型: {sorted(installed_models)}'
    )


def _extract_results(payload):
    """兼容 mem0 不同版本的返回结构。"""
    if isinstance(payload, dict):
        results = payload.get('results')
        if isinstance(results, list):
            return results
    if isinstance(payload, list):
        return payload
    return []


def _memory_text(item: dict) -> str:
    """兼容 mem0 历史字段名。"""
    return item.get('memory') or item.get('text') or item.get('content') or ''


def _ensure_session_state_file() -> str:
    """确保 SESSION-STATE 文件存在，并返回当前内容。"""
    if SESSION_STATE_PATH.exists():
        return SESSION_STATE_PATH.read_text(encoding='utf-8')

    return (
        '# SESSION-STATE.md\n\n'
        '**Status:** Active  \n'
        f'**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n'
        '---\n\n'
        '## Current Task\n\n'
        '- (none)\n\n'
        '## User Context\n\n'
        '- (none)\n\n'
        '## Active Decisions\n\n'
        '- (none)\n\n'
        '## Key Details\n\n'
        '- (none)\n\n'
        '## Danger Zone Log\n\n'
        '**(At 60% context, append exchanges here)**\n'
    )


def _update_session_state(user_id: str, content: str, priority: int, trigger_types: list[str]) -> None:
    """将会话级信息写入 SESSION-STATE.md。"""
    current = _ensure_session_state_file()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    trigger_label = '/'.join(trigger_types) if trigger_types else '未分类'
    entry = f'- {timestamp} | {user_id} | P{priority} | {trigger_label} | {content}'

    if '**Last Updated:**' in current:
        lines = current.splitlines()
        for index, line in enumerate(lines):
            if line.startswith('**Last Updated:**'):
                lines[index] = f'**Last Updated:** {timestamp}'
                break
        current = '\n'.join(lines)

    section_title = '## Memory Captures'
    if section_title not in current:
        if not current.endswith('\n'):
            current += '\n'
        current += f'\n---\n\n{section_title}\n\n'

    current = current.rstrip() + '\n\n' + entry + '\n'
    SESSION_STATE_PATH.write_text(current, encoding='utf-8')


def get_memory():
    """获取mem0实例"""
    _ensure_ollama_ready()
    llm_model = _pick_available_model(['qwen2.5:1.5b', 'qwen2.5:latest'], 'LLM')
    embedder_model = _pick_available_model(['nomic-embed-text:latest', 'nomic-embed-text'], 'Embedder')

    config = MemoryConfig(
        llm=LlmConfig(provider='ollama', config={
            'model': llm_model,
            'ollama_base_url': OLLAMA_BASE_URL
        }),
        embedder=EmbedderConfig(provider='ollama', config={
            'model': embedder_model,
            'ollama_base_url': OLLAMA_BASE_URL
        }),
        vector_store=VectorStoreConfig(provider='chroma', config={
            'path': '/root/.mem0/chroma_db'
        })
    )
    m = Memory(config=config)
    return m


def add_memory(user_id: str, content: str, metadata: dict = None):
    """添加记忆（使用触发引擎自动识别存储类型）"""
    # 使用触发引擎分析
    from trigger_engine import decide_storage, format_memory_content, analyze_triggers

    triggers = analyze_triggers(content)
    memory_type, descriptions, priority = decide_storage(content)
    formatted_content = format_memory_content(content, triggers)

    if metadata is None:
        metadata = {
            "user_id": user_id,
            "source": "mem0-memory",
            "raw_text": content,
            "priority": f"P{priority}",
            "trigger_types": ",".join([t["type"] for t in triggers]),
            "descriptions": "; ".join(descriptions)
        }
    else:
        metadata["user_id"] = user_id
        metadata.setdefault("source", "mem0-memory")
        metadata["raw_text"] = content
        metadata["priority"] = f"P{priority}"
        metadata["trigger_types"] = ",".join([t["type"] for t in triggers])
        metadata["descriptions"] = "; ".join(descriptions)

    trigger_types = [t["type"] for t in triggers]
    stored_to = []

    if memory_type.value in {'session_state', 'both'}:
        _update_session_state(user_id, content, priority, trigger_types)
        stored_to.append('session_state')

    result = None
    memory_id = None
    if memory_type.value in {'mem0_add', 'both'}:
        m = get_memory()
        result = m.add(
            formatted_content,
            user_id=user_id,
            metadata=metadata,
            infer=False,
        )
        results = _extract_results(result)
        if results:
            memory_id = results[0].get('id')
        stored_to.append('mem0')

    return {
        "id": memory_id,
        "priority": f"P{priority}",
        "trigger_types": trigger_types,
        "memory_type": memory_type.value,
        "stored_to": stored_to,
        "result_count": len(_extract_results(result)) if result is not None else 0,
    }


def search_memory(user_id: str, query: str, limit: int = 5):
    """搜索记忆"""
    m = get_memory()
    results = _extract_results(m.search(query=query, user_id=user_id, limit=limit))

    # 解析结果，添加触发信息
    parsed = []
    for r in results:
        metadata = r.get('metadata', {})
        parsed.append({
            'id': r.get('id'),
            'text': _memory_text(r),
            'priority': metadata.get('priority', 'N/A'),
            'trigger_types': metadata.get('trigger_types', 'N/A'),
            'created_at': r.get('created_at')
        })
    
    return parsed


def get_all_memories(user_id: str):
    """获取用户所有记忆"""
    m = get_memory()
    return _extract_results(m.get_all(user_id=user_id))


def chat_with_memory(user_id: str, query: str, limit: int = 5):
    """检索记忆并生成回答"""
    m = get_memory()

    # 检索相关记忆
    memories = _extract_results(m.search(query=query, user_id=user_id, limit=limit))

    # 构建上下文
    context = "\n".join([f"- {_memory_text(mem)}" for mem in memories])

    # 生成回答（使用Ollama直接调用）
    llm_model = _pick_available_model(['qwen2.5:1.5b', 'qwen2.5:latest'], 'LLM')

    prompt = f"""根据以下记忆回答用户问题。如果记忆不相关，直接回答问题。

记忆：
{context}

用户问题：{query}

回答："""
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 500
                }
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '生成失败')
        else:
            answer = f"生成回答失败: {response.status_code}"
    except Exception as e:
        answer = f"调用异常: {str(e)}"
    
    return {
        "answer": answer,
        "memories": memories
    }


def main():
    parser = argparse.ArgumentParser(description='mem0-memory 技能封装')
    parser.add_argument('command', choices=['add', 'search', 'get_all', 'chat', 'reset'],
                        help='命令')
    parser.add_argument('user_id', help='用户ID')
    parser.add_argument('content', nargs='?', help='内容(用于add/search/chat)')
    parser.add_argument('--limit', type=int, default=5, help='限制返回数量')
    
    args = parser.parse_args()

    try:
        if args.command == 'add':
            if not args.content:
                print("错误: add 命令需要内容参数")
                sys.exit(1)
            result = add_memory(args.user_id, args.content)
            print(f"添加成功: {result}")

        elif args.command == 'search':
            if not args.content:
                print("错误: search 命令需要查询内容")
                sys.exit(1)
            results = search_memory(args.user_id, args.content, args.limit)
            print(f"找到 {len(results)} 条记忆:")
            for r in results:
                print(f"  [{r.get('priority', 'N/A')}] {r['text'][:80]}...")
                print(f"    触发: {r.get('trigger_types', 'N/A')}")

        elif args.command == 'get_all':
            results = get_all_memories(args.user_id)
            print(f"用户 {args.user_id} 共有 {len(results)} 条记忆:")
            for r in results:
                print(f"  - {_memory_text(r)[:100]}...")

        elif args.command == 'chat':
            if not args.content:
                print("错误: chat 命令需要问题内容")
                sys.exit(1)
            result = chat_with_memory(args.user_id, args.content, args.limit)
            print(f"回答: {result['answer']}")
            print(f"\n参考记忆:")
            for mem in result['memories']:
                print(f"  - {_memory_text(mem)[:80]}...")

        elif args.command == 'reset':
            print("重置功能已禁用，请手动删除 /root/.mem0/")
            sys.exit(1)
    except Mem0WrapperError as exc:
        print(f"mem0-memory 错误: {exc}")
        sys.exit(1)


if __name__ == '__main__':
    main()
