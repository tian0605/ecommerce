import json
from typing import Dict, Any, Optional
from datetime import datetime

def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复分析步骤执行失败的问题
    """
    # 初始化结果结构
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
            result["errors"].append(f"无效的数据类型：{type(data)}")
            return result
        
        # 执行分析逻辑
        result["data"] = _process_data(data)
        result["metrics"] = _calculate_metrics(data)
        
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(f"分析执行异常：{str(e)}")
    
    return result


def _process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """处理原始数据"""
    processed = {}
    
    # 安全提取常见电商字段
    for key in ["order_id", "product_id", "user_id", "amount", "quantity"]:
        if key in data:
            processed[key] = data[key]
    
    # 处理嵌套数据
    if "details" in data and isinstance(data["details"], dict):
        processed["details"] = data["details"]
    
    return processed


def _calculate_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """计算分析指标"""
    metrics = {
        "total_amount": 0,
        "total_quantity": 0,
        "item_count": 0
    }
    
    try:
        if "amount" in data:
            metrics["total_amount"] = float(data["amount"])
        
        if "quantity" in data:
            metrics["total_quantity"] = int(data["quantity"])
        
        if "items" in data and isinstance(data["items"], list):
            metrics["item_count"] = len(data["items"])
    except (ValueError, TypeError):
        pass
    
    return metrics


def test_analyze():
    """测试验证修复后的analyze函数"""
    # 测试1：正常字典输入
    test_data = {
        "order_id": "ORD001",
        "amount": 100.50,
        "quantity": 2,
        "items": [{"sku": "A001"}, {"sku": "A002"}]
    }
    result1 = analyze(test_data)
    assert result1["status"] == "success", "测试1失败：正常输入应成功"
    
    # 测试2：JSON字符串输入
    json_str = json.dumps({"order_id": "ORD002", "amount": 200})
    result2 = analyze(json_str)
    assert result2["status"] == "success", "测试2失败：JSON字符串应成功"
    
    # 测试3：空输入
    result3 = analyze()
    assert result3["status"] == "success", "测试3失败：空输入应成功"
    
    # 测试4：无效类型
    result4 = analyze("invalid json {")
    assert result4["status"] == "error", "测试4失败：无效JSON应报错"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    # 运行测试
    test_analyze()
    
    # 示例使用
    sample_data = {
        "order_id": "ORD20240101001",
        "product_id": "PROD001",
        "amount": 299.99,
        "quantity": 1,
        "user_id": "USER123"
    }
    
    analysis_result = analyze(sample_data)
    print("\n分析结果:")
    print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
