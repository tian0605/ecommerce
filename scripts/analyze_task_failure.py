#!/usr/bin/env python3
"""
错误分类与诊断分析器

枚举错误类型：
- error_fix_pending: 技术性错误，需修复后再重试（如代码bug、导入错误）
- normal_crash: 客观问题错误，可重试（如网络抖动、超时）
- requires_manual_processing: 需人工介入（如Cookie过期、业务逻辑异常、登录失效）
"""
import sys
import re
from pathlib import Path
from datetime import datetime

# 错误分类规则
ERROR_RULES = [
    # (模式, 类型, 建议)
    (r"ModuleNotFoundError|ImportError|No module named", "error_fix_pending", "Python模块导入失败，需修复代码"),
    (r"SyntaxError|IndentationError|NameError", "error_fix_pending", "Python语法/代码错误，需修复代码"),
    
    (r"EPIPE|Broken pipe|PipeTransport", "normal_crash", "浏览器进程崩溃，可能内存不足"),
    (r"Timeout|timed out|timeout", "normal_crash", "操作超时，网络可能不稳定"),
    (r"Connection refused|Connection reset|Network is unreachable", "normal_crash", "网络连接问题，可重试"),
    (r"ECONNREFUSED|ETIMEDOUT|EHOSTUNREACH", "normal_crash", "网络错误，可重试"),
    
    (r"Cookie.*expire|cookie.*invalid|登录失效|unauthorized", "requires_manual_processing", "Cookie失效，需重新获取"),
    (r"需要登录|not logged|未登录|login required", "requires_manual_processing", "需要人工登录验证"),
    (r"403|401|Forbidden|Unauthorized", "requires_manual_processing", "权限问题，可能需要刷新Cookie"),
    (r"商品不存在|404|product.*not.*found", "requires_manual_processing", "商品不存在或已下架"),
]

def classify_error(content: str) -> dict:
    """根据错误内容分类"""
    result = {
        "error_type": None,
        "error_message": None,
        "suggestion": None,
        "action": None,  # retry | skip | manual
        "timestamp": datetime.now().isoformat()
    }
    
    # 提取错误信息
    error_msg = extract_error_message(content)
    result["error_message"] = error_msg
    
    # 应用分类规则
    for pattern, err_type, suggestion in ERROR_RULES:
        if re.search(pattern, content, re.IGNORECASE):
            result["error_type"] = err_type
            result["suggestion"] = suggestion
            break
    
    # 确定动作
    if result["error_type"] == "error_fix_pending":
        result["action"] = "skip"  # 跳过，等修复
    elif result["error_type"] == "normal_crash":
        result["action"] = "retry"  # 可重试
    elif result["error_type"] == "requires_manual_processing":
        result["action"] = "manual"  # 需人工处理
    else:
        # 未知错误，按可重试处理
        result["error_type"] = "unknown"
        result["action"] = "retry"
        result["suggestion"] = "未知错误，建议检查日志"
    
    return result

def extract_error_message(content: str) -> str:
    """从日志中提取关键错误信息"""
    lines = content.strip().split('\n')
    
    # 优先查找Exception/Error行
    for line in lines:
        if 'Traceback' in line:
            continue
        if 'Error' in line or 'ERROR' in line or 'Exception' in line or '❌' in line:
            # 清理ANSI颜色码
            clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
            clean = clean.strip()
            if len(clean) > 5:
                return clean[:200]  # 限制长度
    
    # 返回最后一行
    for line in reversed(lines):
        clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
        clean = clean.strip()
        if len(clean) > 10:
            return clean[:200]
    
    return "未知错误"

def analyze_workflow_failure(log_file: str) -> dict:
    """分析工作流失败原因"""
    if not Path(log_file).exists():
        return {
            "error": "日志文件不存在",
            "action": "retry",
            "error_type": "unknown"
        }
    
    content = Path(log_file).read_text()
    
    # 获取最后执行步骤
    step_matches = list(re.finditer(r'\[步骤(\d+)\]|\[Step (\d+)\]', content))
    last_step = None
    if step_matches:
        last = step_matches[-1]
        last_step = last.group(1) or last.group(2)
    
    result = classify_error(content)
    result["last_step"] = last_step
    
    # 获取工作流汇总
    summary = {}
    for line in content.split('\n'):
        if ': ❌' in line or ': ✅' in line or ': ⚠️' in line:
            parts = line.split(':')
            if len(parts) >= 2:
                step_name = parts[0].strip()
                status = parts[1].strip() if len(parts) >= 2 else ""
                summary[step_name] = status
    
    result["summary"] = summary
    
    return result

def decide_next_action(analysis: dict, task_state: dict = None) -> dict:
    """根据分析结果决定下一步动作"""
    action = analysis.get("action", "retry")
    
    decisions = {
        "retry": {
            "should_execute": True,
            "message": "客观错误，可重试",
            "notify": True,
            "notify_message": None
        },
        "skip": {
            "should_execute": False,
            "message": f"技术错误需修复: {analysis.get('suggestion')}",
            "notify": True,
            "notify_message": f"⚠️ TC-FLOW-001 阻塞\n错误类型: {analysis.get('error_type')}\n原因: {analysis.get('suggestion')}\n请修复后再执行"
        },
        "manual": {
            "should_execute": False,
            "message": f"需人工处理: {analysis.get('suggestion')}",
            "notify": True,
            "notify_message": f"🚨 TC-FLOW-001 需要人工介入\n错误类型: {analysis.get('error_type')}\n原因: {analysis.get('suggestion')}\n请人工处理后再继续"
        }
    }
    
    return decisions.get(action, decisions["retry"])

if __name__ == '__main__':
    log_file = sys.argv[1] if len(sys.argv) > 1 else '/root/.openclaw/workspace-e-commerce/logs/task_exec.log'
    
    analysis = analyze_workflow_failure(log_file)
    
    print("=" * 50)
    print("错误分析报告")
    print("=" * 50)
    print(f"错误类型: {analysis.get('error_type', 'unknown')}")
    print(f"错误消息: {analysis.get('error_message', 'N/A')}")
    print(f"建议: {analysis.get('suggestion', 'N/A')}")
    print(f"建议动作: {analysis.get('action', 'retry')}")
    if analysis.get('last_step'):
        print(f"最后步骤: Step {analysis.get('last_step')}")
    print("=" * 50)
    
    # 输出机器可读的key=value格式供shell使用
    print(f"\nerror_type={analysis.get('error_type', 'unknown')}")
    print(f"action={analysis.get('action', 'retry')}")

def main():
    log_file = sys.argv[1] if len(sys.argv) > 1 else '/root/.openclaw/workspace-e-commerce/logs/task_exec.log'
    analysis = analyze_workflow_failure(log_file)
    decision = decide_next_action(analysis)
    
    print("=" * 50)
    print("错误分析报告")
    print("=" * 50)
    print(f"错误类型: {analysis.get('error_type', 'unknown')}")
    print(f"错误消息: {analysis.get('error_message', 'N/A')}")
    print(f"原因: {analysis.get('suggestion', 'N/A')}")
    print(f"建议动作: {decision.get('message', 'N/A')}")
    if analysis.get('last_step'):
        print(f"最后步骤: Step {analysis.get('last_step')}")
    print("=" * 50)
    
    # 输出机器可读的key=value格式供shell使用
    print(f"\nerror_type={analysis.get('error_type', 'unknown')}")
    print(f"action={decision.get('action', 'retry')}")
    print(f"原因:{analysis.get('suggestion', 'N/A')}")
