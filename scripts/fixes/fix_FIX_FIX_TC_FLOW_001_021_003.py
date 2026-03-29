import json
from typing import Dict, Any, Optional

def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析步骤修复版本
    修复常见问题：空值处理、参数验证、异常捕获
    """
    result = {
        "status": "success",
        "data": {},
        "message": "分析完成"
    }
    
    try:
        # 1. 处理输入数据为空的情况
        if data is None:
            data = kwargs.get("input_data", {})
        
        # 2. 如果传入的是字符串，尝试解析为字典
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result["status"] = "error"
                result["message"] = f"JSON解析失败: {str(e)}"
                return result
        
        # 3. 确保data是字典类型
        if not isinstance(data, dict):
            result["status"] = "error"
            result["message"] = f"输入数据类型错误，期望dict，得到{type(data)}"
            return result
        
        # 4. 执行分析逻辑（示例：统计关键指标）
        analysis_result = {
            "total_items": len(data.get("items", [])),
            "total_orders": len(data.get("orders", [])),
            "has_user_info": bool(data.get("user_id")),
            "timestamp": data.get("timestamp", ""),
            "metrics": {}
        }
        
        # 5. 计算关键指标
        if "items" in data and isinstance(data["items"], list):
            analysis_result["metrics"]["item_count"] = len(data["items"])
            analysis_result["metrics"]["total_value"] = sum(
                item.get("price", 0) * item.get("quantity", 1) 
                for item in data["items"] 
                if isinstance(item, dict)
            )
        
        if "orders" in data and isinstance(data["orders"], list):
            analysis_result["metrics"]["order_count"] = len(data["orders"])
            analysis_result["metrics"]["completed_orders"] = sum(
                1 for order in data["orders"] 
                if isinstance(order, dict) and order.get("status") == "completed"
            )
        
        result["data"] = analysis_result
        result["message"] = f"分析完成，处理{analysis_result['total_items']}个商品"
        
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"分析过程异常: {str(e)}"
        result["error_type"] = type(e).__name__
    
    return result


def test_analyze():
    """测试analyze函数修复效果"""
    
    # 测试1：正常数据
    test_data_1 = {
        "user_id": "U001",
        "items": [
            {"name": "商品A", "price": 100, "quantity": 2},
            {"name": "商品B", "price": 50, "quantity": 1}
        ],
        "orders": [
            {"order_id": "O001", "status": "completed"},
            {"order_id": "O002", "status": "pending"}
        ],
        "timestamp": "2024-01-01"
    }
    result_1 = analyze(test_data_1)
    assert result_1["status"] == "success", "测试1失败：正常数据处理"
    
    # 测试2：空数据
    result_2 = analyze(None)
    assert result_2["status"] == "success", "测试2失败：空数据处理"
    
    # 测试3：字符串输入
    result_3 = analyze(json.dumps(test_data_1))
    assert result_3["status"] == "success", "测试3失败：字符串输入处理"
    
    # 测试4：无效JSON字符串
    result_4 = analyze("invalid json")
    assert result_4["status"] == "error", "测试4失败：无效JSON应报错"
    
    # 测试5：非字典类型
    result_5 = analyze([1, 2, 3])
    assert result_5["status"] == "error", "测试5失败：非字典类型应报错"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    test_analyze()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
