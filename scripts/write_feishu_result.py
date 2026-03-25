#!/usr/bin/env python3
"""
写入结果到飞书文档和飞书群
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
FEISHU_DOC_ID = "UVlkd1NHrorLumxC8K7cLMBUnDe"
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/6af7d281-ca31-42c6-ab88-5ba434404fb9"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def build_feishu_content(results, improvements):
    """构建飞书文档格式的内容"""
    lines = [
        f"# 任务执行报告\n",
        f"**时间:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
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
            if data.get("commission_twd"):
                lines.append(f"**佣金:** {data.get('commission_twd')} TWD\n")
            if data.get("total_platform_fee_twd"):
                lines.append(f"**平台费:** {data.get('total_platform_fee_twd')} TWD\n")
            if data.get("gross_profit_twd"):
                lines.append(f"**预估利润:** {data.get('gross_profit_twd')} TWD\n")
            if data.get("compliance"):
                lines.append(f"\n**合规检查:** {data.get('compliance')}\n")
    
    if improvements:
        lines.append(f"\n---\n## 发现的优化项\n")
        for imp in improvements:
            lines.append(f"\n**[{imp.get('priority', 'P0')}] {imp.get('module')}:** {imp.get('issue')}\n")
            lines.append(f"- 建议: {imp.get('action')}\n")
    
    lines.append(f"\n---\n*最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    
    return ''.join(lines)

def write_to_markdown(content):
    """写入本地 markdown 文件"""
    md_file = WORKSPACE / 'logs' / 'task_results_latest.md'
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(content)
    log(f"本地文件: {md_file}")
    return str(md_file)

def send_to_feishu_group(results, improvements):
    """发送摘要到飞书群"""
    lines = [
        f"📊 任务执行报告\n",
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"━━━━━━━━━━━━━━━\n",
    ]
    
    for r in results:
        data = r.get("data", {})
        module = data.get("module", "unknown")
        success = r.get("success", False)
        
        status_icon = "✅" if success else "❌"
        lines.append(f"{status_icon} {module}\n")
        
        if data:
            if data.get("optimized_title"):
                lines.append(f"   标题: {data.get('optimized_title')[:30]}...\n")
            if data.get("suggested_price_twd"):
                lines.append(f"   售价: {data.get('suggested_price_twd')} TWD\n")
            if data.get("gross_profit_twd"):
                lines.append(f"   利润: {data.get('gross_profit_twd')} TWD\n")
    
    if improvements:
        lines.append(f"━━━━━━━━━━━━━━━\n")
        lines.append(f"⚠️ 发现 {len(improvements)} 个问题:\n")
        for imp in improvements:
            lines.append(f"  [{imp.get('priority', 'P0')}] {imp.get('module')}: {imp.get('issue')}\n")
    
    lines.append(f"━━━━━━━━━━━━━━━\n")
    lines.append(f"📄 完整报告: https://pcn0wtpnjfsd.feishu.cn/docx/{FEISHU_DOC_ID}")
    
    message = ''.join(lines)
    
    import urllib.request
    
    payload = json.dumps({
        "msg_type": "text",
        "content": {"text": message}
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            FEISHU_WEBHOOK,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('code') == 0:
                log("✅ 飞书群通知发送成功")
                return True
            else:
                log(f"⚠️ 飞书群通知失败")
                return False
    except Exception as e:
        log(f"⚠️ 飞书群通知失败: {e}")
        return False

def write_to_feishu(results, improvements):
    """写入飞书文档并发送通知"""
    # 1. 构建内容
    content = build_feishu_content(results, improvements)
    
    # 2. 写入本地文件
    write_to_markdown(content)
    
    # 3. 发送飞书群通知
    send_to_feishu_group(results, improvements)
    
    # 4. 生成 OpenClaw 命令用于写入飞书文档
    # 由于 Python 无法直接调用 feishu_doc 工具，输出命令供手动执行
    log(f"📄 完整报告已保存，请手动同步到飞书文档")
    log(f"URL: https://pcn0wtpnjfsd.feishu.cn/docx/{FEISHU_DOC_ID}")
    
    # 输出 JSON 格式结果，供外部程序读取
    output = {
        "content": content,
        "doc_url": f"https://pcn0wtpnjfsd.feishu.cn/docx/{FEISHU_DOC_ID}",
        "markdown_file": str(WORKSPACE / 'logs' / 'task_results_latest.md')
    }
    print(f"\n__FEISHU_CONTENT__:{json.dumps(output, ensure_ascii=False)}")
    
    return output

if __name__ == '__main__':
    import sys
    import json
    
    if len(sys.argv) > 1:
        # 从 stdin 读取 results JSON
        try:
            data = json.loads(sys.argv[1])
            results = data.get('results', [])
            improvements = data.get('improvements', [])
        except:
            results = []
            improvements = []
    else:
        results = []
        improvements = []
    
    write_to_feishu(results, improvements)
