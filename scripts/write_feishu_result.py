#!/usr/bin/env python3
"""
写入结果到飞书文档
"""

import urllib.request
import urllib.error
import json
from datetime import datetime

FEISHU_DOC_ID = "UVlkd1NHrorLumxC8K7cLMBUnDe"

def write_results(results, improvements):
    """将测试结果写入飞书文档"""
    
    # 构建飞书文档内容
    blocks = []
    
    # 标题
    blocks.append({
        "block_type": 2,  # heading1
        "heading1": {"elements": [{"type": "text_run", "text_run": {"content": f"任务执行报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"}}], "style": {}}
    })
    
    # 分隔线
    blocks.append({"block_type": 12, "table": {}})  # hr
    
    # 执行结果
    blocks.append({
        "block_type": 2,
        "heading1": {"elements": [{"type": "text_run", "text_run": {"content": "执行结果"}}], "style": {}}
    })
    
    for r in results:
        data = r.get("data", {})
        module = data.get("module", "")
        
        blocks.append({
            "block_type": 3,
            "heading2": {"elements": [{"type": "text_run", "text_run": {"content": f"◆ {module}"}}], "style": {}}
        })
        
        blocks.append({
            "block_type": 6,
            "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": f"状态: {r.get('success', False)} - {r.get('message', '')}"}}], "style": {}}
        })
        
        if data:
            if data.get("optimized_title"):
                blocks.append({
                    "block_type": 6,
                    "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": f"优化标题: {data.get('optimized_title', '')}"}}], "style": {}}
                })
            
            if data.get("suggested_price_twd"):
                blocks.append({
                    "block_type": 6,
                    "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": f"建议售价: {data.get('suggested_price_twd')} TWD"}}], "style": {}}
                })
            
            if data.get("compliance"):
                blocks.append({
                    "block_type": 6,
                    "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": f"合规检查: {data.get('compliance', '')}"}}], "style": {}}
                })
    
    # 优化项
    if improvements:
        blocks.append({
            "block_type": 12,
            "table": {}
        })
        
        blocks.append({
            "block_type": 2,
            "heading1": {"elements": [{"type": "text_run", "text_run": {"content": "发现的优化项"}}], "style": {}}
        })
        
        for imp in improvements:
            blocks.append({
                "block_type": 6,
                "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": f"[{imp['priority']}] {imp['module']}: {imp['issue']}"}}], "style": {}}
            })
            blocks.append({
                "block_type": 6,
                "paragraph": {"elements": [{"type": "text_run", "text_run": {"content": f"   建议: {imp['action']}"}}], "style": {}}
            })
    
    # 更新飞书文档
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{FEISHU_DOC_ID}/blocks"
    
    payload = json.dumps({"children": blocks}).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer '  # 需要 access token
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"飞书文档更新结果: {result.get('code')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"飞书文档更新失败 (HTTP {e.code}): {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"飞书文档更新失败: {e}")
        return False

if __name__ == '__main__':
    # 测试
    write_results([
        {
            "step": "listing-optimizer",
            "success": True,
            "message": "测试完成",
            "data": {
                "module": "listing-optimizer",
                "status": "✅",
                "optimized_title": "测试标题",
                "compliance": "✅ 无违规"
            }
        }
    ], [
        {"priority": "P1", "module": "test", "issue": "测试问题", "action": "测试修复"}
    ])
