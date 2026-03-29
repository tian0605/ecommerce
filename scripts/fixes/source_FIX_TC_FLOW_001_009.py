import json
from typing import Dict, Any, Optional
from datetime import datetime

def analyze(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复了空值处理、类型验证和异常捕获问题
    """
    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "data": {},
        "errors": []
    }
    
    try:
        # 1. 处理空数据情况
        if data is None:
            result["status"] = "warning"
            result["errors"].append("输入数据为空")
            return result
        
        # 2. 处理字符串类型的输入
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result["status"] = "error"
                result["errors"].append(f"JSON解析失败: {str(e)}")
                return result
        
        # 3. 验证数据类型
        if not isinstance(data, dict):
            result["status"] = "error"
            result["errors"].append(f"期望dict类型，收到{type(data).__name__}")
            return result
        
        # 4. 执行分析逻辑
        analysis_result = {
            "total_items": len(data),
            "keys": list(data.keys()),
            "has_required_fields": True
        }
        
        # 5. 检查必要字段（电商常见字段）
        required_fields = ["order_id", "product_id", "quantity", "price"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            analysis_result["has_required_fields"] = False
            analysis_result["missing_fields"] = missing_fields
            result["status"] = "warning"
            result["errors"].append(f"缺少必要字段: {missing_fields}")
        
        # 6. 数值字段验证
        numeric_fields = ["quantity", "price", "amount"]
        for field in numeric_fields:
            if field in data:
                try:
                    analysis_result[f"{field}_valid"] = float(data[field]) >= 0
                except (ValueError, TypeError):
                    analysis_result[f"{field}_valid"] = False
                    result["errors"].append(f"字段{field}数值验证失败")
        
        result["data"] = analysis_result
        
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(f"分析过程异常: {str(e)}")
    
    return result


def test_analyze_fix():
    """测试修复后的analyze函数"""
    test_cases = [
        # 测试1: 正常数据
        ({"order_id": "001", "product_id": "P001", "quantity": 2, "price": 99.9}, "success"),
        # 测试2: 空数据
        (None, "warning"),
        # 测试3: 字符串JSON
        ('{"order_id": "002", "quantity": 1}', "warning"),
        # 测试4: 缺少必要字段
        ({"order_id": "003"}, "warning"),
        # 测试5: 无效类型
        ([1, 2, 3], "error"),
    ]
    
    all_passed = True
    for i, (input_data, expected_status) in enumerate(test_cases, 1):
        result = analyze(input_data)
        if result["status"] != expected_status:
            print(f"测试{i}失败: 期望{expected_status}, 得到{result['status']}")
            all_passed = False
        else:
            print(f"测试{i}通过")
    
    return all_passed


if __name__ == "__main__":
    # 运行测试
    print("开始测试analyze函数修复...")
    success = test_analyze_fix()
    print(f"\n所有测试{'通过' if success else '失败'}")
    
    # 示例调用
    print("\n示例调用:")
    sample_data = {
        "order_id": "ORD-2024-001",
        "product_id": "PROD-888",
        "quantity": 5,
        "price": 199.00
    }
    result = analyze(sample_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
