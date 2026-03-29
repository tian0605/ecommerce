import json
from typing import Any, Dict, Optional, Union

def analyze(data: Optional[Union[str, Dict, list]]) -> Dict[str, Any]:
    """
    电商运营数据分析函数修复版本
    处理各种输入格式，确保稳定运行
    """
    # 1. 处理None输入
    if data is None:
        return {"status": "error", "message": "输入数据为空", "result": {}}
    
    # 2. 处理字符串输入（可能是JSON格式）
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return {
                "status": "error", 
                "message": f"JSON解析失败: {str(e)}", 
                "result": {}
            }
    
    # 3. 验证数据类型
    if not isinstance(data, (dict, list)):
        return {
            "status": "error", 
            "message": f"不支持的数据类型: {type(data).__name__}", 
            "result": {}
        }
    
    # 4. 执行分析逻辑
    try:
        result = _perform_analysis(data)
        return {
            "status": "success",
            "message": "分析完成",
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"分析过程异常: {str(e)}",
            "result": {}
        }


def _perform_analysis(data: Union[Dict, list]) -> Dict[str, Any]:
    """
    执行实际的数据分析逻辑
    """
    result = {
        "data_type": type(data).__name__,
        "record_count": 0,
        "metrics": {}
    }
    
    # 处理列表数据
    if isinstance(data, list):
        result["record_count"] = len(data)
        if data and isinstance(data[0], dict):
            result["metrics"] = _analyze_dict_list(data)
    
    # 处理字典数据
    elif isinstance(data, dict):
        result["record_count"] = len(data)
        result["metrics"] = _analyze_dict_data(data)
    
    return result


def _analyze_dict_list(data: list) -> Dict[str, Any]:
    """分析字典列表数据"""
    metrics = {
        "fields": list(data[0].keys()) if data else [],
        "sample": data[0] if data else {}
    }
    return metrics


def _analyze_dict_data(data: dict) -> Dict[str, Any]:
    """分析字典数据"""
    metrics = {
        "keys": list(data.keys()),
        "has_nested": any(isinstance(v, (dict, list)) for v in data.values())
    }
    return metrics


# 测试验证
def test_fix():
    """测试修复后的analyze函数"""
    test_cases = [
        # 测试None输入
        (None, "error"),
        # 测试字符串JSON输入
        ('{"order_id": "123", "amount": 100}', "success"),
        # 测试字典输入
        ({"order_id": "123", "amount": 100}, "success"),
        # 测试列表输入
        ([{"order_id": "123"}, {"order_id": "124"}], "success"),
        # 测试无效JSON字符串
        ('invalid json', "error"),
    ]
    
    all_passed = True
    for test_data, expected_status in test_cases:
        result = analyze(test_data)
        if result.get("status") != expected_status:
            print(f"测试失败: {test_data}")
            all_passed = False
    
    if all_passed:
        print("所有测试通过!")
    
    return all_passed


if __name__ == "__main__":
    # 运行测试
    test_fix()
    
    # 示例使用
    sample_data = '{"orders": [{"id": 1, "status": "paid"}, {"id": 2, "status": "pending"}]}'
    result = analyze(sample_data)
    print(f"\n分析结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
