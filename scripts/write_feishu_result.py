#!/usr/bin/env python3
"""
写入结果到飞书文档和飞书群
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime

from notification_service import append_text_to_docx, get_docx_url, send_feishu_text

WORKSPACE = Path('/root/.openclaw/workspace-e-commerce')
FEISHU_DOC_ID = "UVlkd1NHrorLumxC8K7cLMBUnDe"

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
    
    if send_feishu_text(message):
        log("✅ 飞书群通知发送成功")
        return True

    log("⚠️ 飞书群通知失败")
    return False

def write_to_feishu(results, improvements, task_name=None):
    """写入飞书文档并发送通知"""
    # 1. 构建内容
    content = build_feishu_content(results, improvements)
    
    # 2. 写入本地文件
    markdown_file = write_to_markdown(content)
    
    # 3. 自动写入飞书文档
    doc_sync_success = False
    doc_sync_error = None
    doc_url = get_docx_url(FEISHU_DOC_ID)
    try:
        append_result = append_text_to_docx(FEISHU_DOC_ID, content)
        doc_sync_success = append_result.get('success', False)
        doc_url = append_result.get('url', doc_url)
        log(f"📄 飞书文档自动写入成功: {doc_url}")
    except Exception as exc:
        doc_sync_error = str(exc)
        log(f"⚠️ 飞书文档自动写入失败: {doc_sync_error}")

    # 4. 发送飞书群通知
    group_notify_success = send_to_feishu_group(results, improvements)

    # 5. 如有 task_name，则写回任务审计
    if task_name:
        from task_manager import TaskManager

        tm = TaskManager()
        try:
            tm.record_feedback_artifacts(task_name, doc_url=doc_url, markdown_file=markdown_file)
            tm.record_notification(
                task_name=task_name,
                event='task_report_doc_sync',
                message=f'任务报告同步到飞书文档: {doc_url}',
                success=doc_sync_success,
                error=doc_sync_error,
                metadata={'markdown_file': markdown_file},
            )
            tm.record_notification(
                task_name=task_name,
                event='task_report_group_notify',
                message=f'任务报告摘要已发送到飞书群: {doc_url}',
                success=group_notify_success,
                error=None if group_notify_success else '飞书群摘要发送失败',
                metadata={'doc_url': doc_url},
            )
        finally:
            tm.close()
    
    # 输出 JSON 格式结果，供外部程序读取
    output = {
        "content": content,
        "doc_url": doc_url,
        "markdown_file": markdown_file,
        "doc_sync_success": doc_sync_success,
        "doc_sync_error": doc_sync_error,
        "group_notify_success": group_notify_success,
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
            task_name = data.get('task_name')
        except:
            results = []
            improvements = []
            task_name = None
    else:
        results = []
        improvements = []
        task_name = None
    
    write_to_feishu(results, improvements, task_name=task_name)
