import json
from datetime import datetime
from typing import Dict, Any, Optional

def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复了参数验证、异常处理和返回值格式问题
    """
    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "data": {},
        "metrics": {},
        "errors": []
    }
    
    try:
        # 参数验证和初始化
        if data is None:
            data = kwargs.get("data", {})
        
        # 处理字符串类型的输入
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result["status"] = "error"
                result["errors"].append(f"JSON解析失败：{str(e)}")
                return result
        
        # 确保data是字典类型
        if not isinstance(data, dict):
            result["status"] = "error"
            result["errors"].append("输入数据必须是字典或可解析的JSON字符串")
            return result
        
        # 执行分析逻辑
        result["data"] = _process_data(data)
        result["metrics"] = _calculate_metrics(data)
        
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(f"分析执行失败：{str(e)}")
    
    return result


def _process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """处理原始数据"""
    processed = {}
    
    # 处理订单数据
    if "orders" in data:
        processed["order_count"] = len(data["orders"])
        processed["orders"] = data["orders"]
    
    # 处理商品数据
    if "products" in data:
        processed["product_count"] = len(data["products"])
        processed["products"] = data["products"]
    
    # 处理用户数据
    if "users" in data:
        processed["user_count"] = len(data["users"])
        processed["users"] = data["users"]
    
    return processed


def _calculate_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """计算关键指标"""
    metrics = {
        "total_revenue": 0,
        "avg_order_value": 0,
        "conversion_rate": 0
    }
    
    # 计算总收入
    if "orders" in data:
        total = sum(order.get("amount", 0) for order in data["orders"])
        metrics["total_revenue"] = total
        
        # 计算平均订单价值
        if len(data["orders"]) > 0:
            metrics["avg_order_value"] = total / len(data["orders"])
    
    # 计算转化率
    if "users" in data and "orders" in data:
        if len(data["users"]) > 0:
            metrics["conversion_rate"] = len(data["orders"]) / len(data["users"])
    
    return metrics


# 测试验证
def test_analyze():
    """测试analyze函数"""
    # 测试1：正常字典输入
    test_data = {
        "orders": [
            {"id": 1, "amount": 100},
            {"id": 2, "amount": 200}
        ],
        "users": [
            {"id": 1, "name": "user1"},
            {"id": 2, "name": "user2"},
            {"id": 3, "name": "user3"}
        ]
    }
    
    result = analyze(test_data)
    assert result["status"] == "success", "测试1失败：状态应为success"
    assert result["data"]["order_count"] == 2, "测试1失败：订单数应为2"
    assert result["metrics"]["total_revenue"] == 300, "测试1失败：总收入应为300"
    
    # 测试2：JSON字符串输入
    json_str = json.dumps(test_data)
    result = analyze(json_str)
    assert result["status"] == "success", "测试2失败：JSON字符串解析应成功"
    
    # 测试3：空输入
    result = analyze()
    assert result["status"] == "success", "测试3失败：空输入应返回success"
    
    # 测试4：无效输入
    result = analyze("invalid json")
    assert result["status"] == "error", "测试4失败：无效JSON应返回error"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    test_analyze()
    
    # 示例使用
    sample_data = {
        "orders": [
            {"id": 1, "amount": 150.00},
            {"id": 2, "amount": 280.00},
            {"id": 3, "amount": 95.00}
        ],
        "products": [
            {"id": 1, "name": "商品A"},
            {"id": 2, "name": "商品B"}
        ],
        "users": [
            {"id": 1, "name": "用户1"},
            {"id": 2, "name": "用户2"}
        ]
    }
    
    analysis_result = analyze(sample_data)
    print("\n分析结果:")
    print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
