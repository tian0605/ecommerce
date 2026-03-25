#!/usr/bin/env python3
"""
写入结果到飞书文档
使用 feishu_doc 工具的 REST API 方式写入
"""

import urllib.request
import urllib.error
import json
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
FEISHU_DOC_ID = "UVlkd1NHrorLumxC8K7cLMBUnDe"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def write_to_markdown(results, improvements):
    """先将结果写入 markdown 文件"""
    md_file = WORKSPACE / 'logs' / 'task_results_latest.md'
    
    lines = [
        f"# 任务执行报告\n",
        f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"---\n",
        f"## 执行结果\n",
    ]
    
    for r in results:
        data = r.get("data", {})
        module = data.get("module", "unknown")
        success = r.get("success", False)
        message = r.get("message", "")
        
        status_icon = "✅" if success else "❌"
        lines.append(f"\n### {status_icon} {module}\n")
        lines.append(f"**状态:** {message}\n")
        
        if data:
            if data.get("optimized_title"):
                lines.append(f"\n**优化标题:** {data.get('optimized_title')}\n")
            if data.get("suggested_price_twd"):
                lines.append(f"\n**建议售价:** {data.get('suggested_price_twd')} TWD\n")
            if data.get("compliance"):
                lines.append(f"\n**合规检查:** {data.get('compliance')}\n")
    
    if improvements:
        lines.append(f"\n---\n## 发现的优化项\n")
        for imp in improvements:
            lines.append(f"\n**[{imp.get('priority', 'P0')}] {imp.get('module')}:** {imp.get('issue')}\n")
            lines.append(f"- 建议: {imp.get('action')}\n")
    
    content = ''.join(lines)
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    log(f"结果已写入: {md_file}")
    return str(md_file)

def write_to_feishu(results, improvements):
    """写入飞书文档"""
    # 构建内容（使用飞书文档 API）
    content_parts = []
    
    content_parts.append(f"## 任务执行报告\n")
    content_parts.append(f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    for r in results:
        data = r.get("data", {})
        module = data.get("module", "unknown")
        success = r.get("success", False)
        message = r.get("message", "")
        
        status_icon = "✅" if success else "❌"
        content_parts.append(f"### {status_icon} {module}\n\n")
        content_parts.append(f"- **状态:** {message}\n")
        
        if data:
            if data.get("optimized_title"):
                content_parts.append(f"- **优化标题:** {data.get('optimized_title')}\n")
            if data.get("suggested_price_twd"):
                content_parts.append(f"- **建议售价:** {data.get('suggested_price_twd')} TWD\n")
            if data.get("compliance"):
                content_parts.append(f"- **合规检查:** {data.get('compliance')}\n")
        
        content_parts.append(f"\n---\n")
    
    if improvements:
        content_parts.append(f"\n## 发现的优化项\n")
        for imp in improvements:
            content_parts.append(f"\n**[{imp.get('priority', 'P0')}] {imp.get('module')}:** {imp.get('issue')}\n")
            content_parts.append(f"- 建议: {imp.get('action')}\n")
    
    content = ''.join(content_parts)
    
    # 由于没有 access token，先写入本地文件
    # 等 feishu_doc 工具支持时再调用 API
    md_file = write_to_markdown(results, improvements)
    
    log(f"⚠️ 飞书 API 需要 access token，当前写入本地文件: {md_file}")
    log(f"请手动复制内容到飞书文档: https://feishu.cn/docx/{FEISHU_DOC_ID}")
    
    return md_file

def main():
    """测试写入"""
    results = [
        {
            "step": "listing-optimizer",
            "success": True,
            "message": "listing-optimizer 测试完成",
            "data": {
                "module": "listing-optimizer",
                "status": "✅",
                "optimized_title": "收納 首飾 北歐風 竹編 帶蓋 分格 桌面 髮飾 20x15x10cm 天然竹 米白 免運",
                "compliance": "✅ 无'现货'词汇"
            }
        },
        {
            "step": "miaoshou-updater",
            "success": False,
            "message": "跳过（无优化标题）",
            "data": None
        },
        {
            "step": "profit-analyzer",
            "success": True,
            "message": "profit-analyzer 测试完成",
            "data": {
                "module": "profit-analyzer",
                "status": "✅",
                "suggested_price_twd": 167
            }
        }
    ]
    
    improvements = [
        {
            "priority": "P0",
            "module": "miaoshou-updater",
            "issue": "跳过（无优化标题）",
            "action": "先完成 listing-optimizer 优化"
        }
    ]
    
    write_to_feishu(results, improvements)

if __name__ == '__main__':
    main()
