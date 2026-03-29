#!/usr/bin/env python3
"""
mem0-memory 技能封装
使用 Ollama qwen2.5:latest 作为LLM，Ollama nomic-embed-text 作为embedder
"""
import sys
import argparse
from pathlib import Path

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
sys.path.insert(0, str(WORKSPACE))

from mem0.memory.main import Memory
from mem0.configs.base import MemoryConfig, LlmConfig, EmbedderConfig, VectorStoreConfig

# Ollama 配置
OLLAMA_BASE_URL = "http://localhost:11434"


def get_memory():
    """获取mem0实例"""
    config = MemoryConfig(
        llm=LlmConfig(provider='ollama', config={
            'model': 'qwen2.5:latest',
            'ollama_base_url': OLLAMA_BASE_URL
        }),
        embedder=EmbedderConfig(provider='ollama', config={
            'model': 'nomic-embed-text:latest',
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
    m = get_memory()
    
    # 使用触发引擎分析
    from trigger_engine import decide_storage, format_memory_content, analyze_triggers
    
    triggers = analyze_triggers(content)
    memory_type, descriptions, priority = decide_storage(content)
    formatted_content = format_memory_content(content, triggers)
    
    if metadata is None:
        metadata = {
            "user_id": user_id,
            "priority": f"P{priority}",
            "trigger_types": ",".join([t["type"] for t in triggers]),
            "descriptions": "; ".join(descriptions)
        }
    else:
        metadata["user_id"] = user_id
        metadata["priority"] = f"P{priority}"
        metadata["trigger_types"] = ",".join([t["type"] for t in triggers])
        metadata["descriptions"] = "; ".join(descriptions)
    
    # 添加到 mem0
    result = m.add(formatted_content, user_id=user_id, metadata=metadata)
    
    return {
        "id": result.get("id"),
        "priority": f"P{priority}",
        "trigger_types": [t["type"] for t in triggers],
        "memory_type": memory_type.value
    }


def search_memory(user_id: str, query: str, limit: int = 5):
    """搜索记忆"""
    m = get_memory()
    results = m.search(query=query, user_id=user_id, limit=limit)
    
    # 解析结果，添加触发信息
    parsed = []
    for r in results:
        metadata = r.get('metadata', {})
        parsed.append({
            'id': r.get('id'),
            'text': r.get('text'),
            'priority': metadata.get('priority', 'N/A'),
            'trigger_types': metadata.get('trigger_types', 'N/A'),
            'created_at': r.get('created_at')
        })
    
    return parsed


def get_all_memories(user_id: str):
    """获取用户所有记忆"""
    m = get_memory()
    results = m.get_all(user_id=user_id)
    # mem0返回格式: {'results': [...]}
    return results.get('results', [])


def chat_with_memory(user_id: str, query: str, limit: int = 5):
    """检索记忆并生成回答"""
    m = get_memory()
    
    # 检索相关记忆
    memories = m.search(query=query, user_id=user_id, limit=limit)
    
    # 构建上下文
    context = "\n".join([f"- {mem['text']}" for mem in memories])
    
    # 生成回答（使用Ollama直接调用）
    import requests
    
    prompt = f"""根据以下记忆回答用户问题。如果记忆不相关，直接回答问题。

记忆：
{context}

用户问题：{query}

回答："""
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": "qwen2.5:latest",
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
            print(f"  - {r.get('text', '')[:100]}...")
    
    elif args.command == 'chat':
        if not args.content:
            print("错误: chat 命令需要问题内容")
            sys.exit(1)
        result = chat_with_memory(args.user_id, args.content, args.limit)
        print(f"回答: {result['answer']}")
        print(f"\n参考记忆:")
        for mem in result['memories']:
            print(f"  - {mem['text'][:80]}...")
    
    elif args.command == 'reset':
        print("重置功能已禁用，请手动删除 /root/.mem0/")
        sys.exit(1)


if __name__ == '__main__':
    main()
