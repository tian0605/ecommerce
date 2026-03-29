import json
from typing import Dict, Any, Optional

def analyze(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    电商数据分析函数 - 修复版本
    处理常见的数据异常和边界情况
    """
    # 默认返回结构
    result = {
        "status": "success",
        "data": {},
        "metrics": {},
        "errors": []
    }
    
    try:
        # 1. 处理 None 或空数据
        if data is None:
            result["status"] = "warning"
            result["errors"].append("输入数据为 None")
            return result
        
        # 2. 处理字符串类型的输入（常见于 API 响应）
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result["status"] = "error"
                result["errors"].append(f"JSON 解析失败：{str(e)}")
                return result
        
        # 3. 验证数据类型
        if not isinstance(data, dict):
            result["status"] = "error"
            result["errors"].append(f"期望 dict 类型，实际得到：{type(data).__name__}")
            return result
        
        # 4. 处理空字典
        if len(data) == 0:
            result["status"] = "warning"
            result["errors"].append("输入数据为空字典")
            return result
        
        # 5. 执行分析逻辑
        result["data"] = data
        
        # 计算基础指标
        result["metrics"] = {
            "total_fields": len(data),
            "has_order_id": "order_id" in data,
            "has_amount": "amount" in data,
            "has_status": "status" in data
        }
        
        # 6. 验证必要字段（电商场景常见字段）
        required_fields = ["order_id", "amount", "status"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            result["status"] = "warning"
            result["errors"].append(f"缺少必要字段：{missing_fields}")
        
        return result
        
    except Exception as e:
        # 7. 捕获所有未预期异常
        result["status"] = "error"
        result["errors"].append(f"分析过程异常：{str(e)}")
        return result


def analyze_batch(data_list: list) -> Dict[str, Any]:
    """
    批量数据分析函数
    """
    results = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    if not isinstance(data_list, list):
        results["failed"] = 1
        results["details"].append({"error": "输入必须是列表类型"})
        return results
    
    results["total"] = len(data_list)
    
    for i, item in enumerate(data_list):
        analysis_result = analyze(item)
        results["details"].append({
            "index": i,
            "result": analysis_result
        })
        
        if analysis_result["status"] == "success":
            results["success"] += 1
        else:
            results["failed"] += 1
    
    return results


# 测试验证
def test_fix():
    """测试修复后的 analyze 函数"""
    
    # 测试 1: 正常数据
    test_data = {"order_id": "ORD001", "amount": 100.0, "status": "paid"}
    result = analyze(test_data)
    assert result["status"] == "success"
    assert result["metrics"]["total_fields"] == 3
    
    # 测试 2: None 输入
    result = analyze(None)
    assert result["status"] == "warning"
    
    # 测试 3: 字符串输入
    result = analyze('{"order_id": "ORD002"}')
    assert result["status"] in ["success", "warning"]
    
    # 测试 4: 空字典
    result = analyze({})
    assert result["status"] == "warning"
    
    # 测试 5: 批量分析
    batch_result = analyze_batch([test_data, None, {}])
    assert batch_result["total"] == 3
    
    return True


if __name__ == "__main__":
    # 运行测试
    test_passed = test_fix()
    print(f"测试通过：{test_passed}")
    
    # 示例使用
    sample_data = {
        "order_id": "TC-FLOW-001-012",
        "amount": 299.99,
        "status": "completed",
        "items": 3
    }
    
    result = analyze(sample_data)
    print(f"分析结果：{json.dumps(result, indent=2, ensure_ascii=False)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
