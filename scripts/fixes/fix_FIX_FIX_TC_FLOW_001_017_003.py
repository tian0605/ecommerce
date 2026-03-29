import json
from typing import Dict, Any, Optional
from datetime import datetime

def analyze(data: Any, config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    电商运营数据分析步骤
    修复数据处理的健壮性问题
    """
    result = {
        "status": "success",
        "data": None,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 1. 输入数据验证
        if data is None:
            raise ValueError("输入数据不能为空")
        
        # 2. 处理字符串类型的JSON数据
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON解析失败: {str(e)}")
        
        # 3. 确保数据是字典类型
        if not isinstance(data, dict):
            data = {"raw_data": data}
        
        # 4. 执行数据分析逻辑
        analyzed_data = perform_analysis(data, config)
        
        # 5. 验证分析结果
        if not validate_result(analyzed_data):
            raise ValueError("分析结果验证失败")
        
        result["data"] = analyzed_data
        
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        # 记录错误日志（实际场景中可接入日志系统）
        print(f"[ERROR] analyze步骤失败: {str(e)}")
    
    return result


def perform_analysis(data: Dict, config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    执行实际的数据分析逻辑
    """
    config = config or {}
    
    analysis_result = {
        "metrics": {},
        "summary": {},
        "recommendations": []
    }
    
    # 处理关键指标
    if "sales" in data:
        analysis_result["metrics"]["sales"] = safe_numeric(data["sales"])
    
    if "orders" in data:
        analysis_result["metrics"]["orders"] = safe_numeric(data["orders"])
    
    if "conversion_rate" in data:
        analysis_result["metrics"]["conversion_rate"] = safe_numeric(data["conversion_rate"])
    
    # 生成摘要
    analysis_result["summary"]["total_fields"] = len(data)
    analysis_result["summary"]["processed_at"] = datetime.now().isoformat()
    
    # 生成建议
    if analysis_result["metrics"].get("conversion_rate", 0) < 0.05:
        analysis_result["recommendations"].append("转化率较低，建议优化商品页面")
    
    return analysis_result


def safe_numeric(value: Any) -> float:
    """
    安全转换为数值类型
    """
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def validate_result(result: Dict) -> bool:
    """
    验证分析结果的有效性
    """
    if not isinstance(result, dict):
        return False
    
    required_keys = ["metrics", "summary"]
    for key in required_keys:
        if key not in result:
            return False
    
    return True


# 测试验证
def test_analyze():
    """测试analyze函数的各种场景"""
    
    # 测试1: 正常字典输入
    test_data1 = {"sales": 1000, "orders": 50, "conversion_rate": 0.05}
    result1 = analyze(test_data1)
    assert result1["status"] == "success", "测试1失败"
    
    # 测试2: JSON字符串输入
    test_data2 = '{"sales": 2000, "orders": 100}'
    result2 = analyze(test_data2)
    assert result2["status"] == "success", "测试2失败"
    
    # 测试3: 空值处理
    result3 = analyze(None)
    assert result3["status"] == "failed", "测试3失败"
    
    # 测试4: 带配置的分析
    test_data4 = {"sales": 500, "conversion_rate": 0.03}
    config = {"threshold": 0.05}
    result4 = analyze(test_data4, config)
    assert result4["status"] == "success", "测试4失败"
    
    print("所有测试通过!")
    return True


if __name__ == "__main__":
    test_analyze()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
