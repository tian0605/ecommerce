import json
from typing import Dict, Any, Optional

def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复空数据处理和异常捕获问题
    """
    try:
        # 参数验证和默认值处理
        if data is None:
            data = {}
        
        # 确保data是字典类型
        if isinstance(data, str):
            data = json.loads(data)
        
        if not isinstance(data, dict):
            raise ValueError(f"Invalid data type: {type(data)}, expected dict")
        
        # 执行分析逻辑
        result = {
            "status": "success",
            "data_processed": True,
            "record_count": len(data),
            "analysis_result": {}
        }
        
        # 处理常见电商数据字段
        if "orders" in data:
            result["analysis_result"]["order_count"] = len(data["orders"])
        if "products" in data:
            result["analysis_result"]["product_count"] = len(data["products"])
        if "sales" in data:
            result["analysis_result"]["total_sales"] = sum(data["sales"]) if data["sales"] else 0
        
        # 添加额外参数处理
        for key, value in kwargs.items():
            result["analysis_result"][key] = value
        
        return result
        
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "error_type": "json_parse_error",
            "message": f"JSON解析失败：{str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "unknown_error",
            "message": f"分析失败：{str(e)}"
        }


def test_analyze_fix():
    """测试验证修复后的analyze函数"""
    # 测试1：正常数据
    result1 = analyze({"orders": [1, 2, 3], "sales": [100, 200, 300]})
    assert result1["status"] == "success"
    assert result1["data_processed"] == True
    
    # 测试2：空数据
    result2 = analyze(None)
    assert result2["status"] == "success"
    assert result2["record_count"] == 0
    
    # 测试3：字符串数据
    result3 = analyze('{"products": ["A", "B"]}')
    assert result3["status"] == "success"
    assert result3["analysis_result"]["product_count"] == 2
    
    # 测试4：额外参数
    result4 = analyze({}, filter_date="2024-01-01")
    assert result4["analysis_result"]["filter_date"] == "2024-01-01"
    
    print("所有测试通过！")
    return True


if __name__ == "__main__":
    test_analyze_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
