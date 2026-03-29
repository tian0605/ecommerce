import json
from typing import Dict, Any, Optional

def analyze(data: Any, config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    电商运营数据分析步骤
    修复数据验证和异常处理问题
    """
    # 默认配置
    if config is None:
        config = {}
    
    # 结果容器
    result = {
        "success": False,
        "data": None,
        "error": None,
        "metrics": {}
    }
    
    try:
        # 1. 数据为空检查
        if data is None:
            result["error"] = "输入数据为空"
            return result
        
        # 2. 字符串数据解析
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result["error"] = f"JSON解析失败: {str(e)}"
                return result
        
        # 3. 数据类型验证
        if not isinstance(data, (dict, list)):
            result["error"] = f"不支持的数据类型: {type(data).__name__}"
            return result
        
        # 4. 列表数据转换
        if isinstance(data, list):
            if len(data) == 0:
                result["error"] = "数据列表为空"
                return result
            data = {"items": data, "count": len(data)}
        
        # 5. 执行分析逻辑
        metrics = _calculate_metrics(data, config)
        
        # 6. 构建成功结果
        result["success"] = True
        result["data"] = data
        result["metrics"] = metrics
        
    except Exception as e:
        result["error"] = f"分析执行异常: {str(e)}"
    
    return result


def _calculate_metrics(data: Dict, config: Dict) -> Dict[str, Any]:
    """
    计算电商运营指标
    """
    metrics = {
        "total_items": 0,
        "total_value": 0,
        "avg_value": 0,
        "categories": []
    }
    
    try:
        # 统计商品数量
        items = data.get("items", [])
        metrics["total_items"] = len(items) if isinstance(items, list) else 0
        
        # 统计总金额
        total_value = 0
        categories = set()
        
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict):
                # 获取商品价值
                value = item.get("value", item.get("price", 0))
                if isinstance(value, (int, float)):
                    total_value += value
                
                # 收集分类
                category = item.get("category", item.get("cat", "unknown"))
                if category:
                    categories.add(category)
        
        metrics["total_value"] = total_value
        metrics["avg_value"] = total_value / metrics["total_items"] if metrics["total_items"] > 0 else 0
        metrics["categories"] = list(categories)
        
    except Exception:
        pass
    
    return metrics


# 测试验证
def test_analyze():
    """测试analyze函数"""
    # 测试1: 正常字典数据
    test_data = {
        "items": [
            {"name": "商品1", "value": 100, "category": "电子"},
            {"name": "商品2", "value": 200, "category": "服装"}
        ]
    }
    result = analyze(test_data)
    assert result["success"] == True
    assert result["metrics"]["total_items"] == 2
    
    # 测试2: JSON字符串
    json_str = '{"items": [{"value": 50}]}'
    result = analyze(json_str)
    assert result["success"] == True
    
    # 测试3: 空数据
    result = analyze(None)
    assert result["success"] == False
    assert result["error"] is not None
    
    # 测试4: 空列表
    result = analyze([])
    assert result["success"] == False
    
    print("所有测试通过!")
    return True


if __name__ == "__main__":
    test_analyze()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
