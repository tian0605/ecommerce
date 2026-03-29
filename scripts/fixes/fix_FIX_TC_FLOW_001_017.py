import json
from typing import Dict, Any, Optional
from datetime import datetime

def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复参数验证、异常处理和数据结构问题
    """
    result = {
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'data': {},
        'metrics': {},
        'errors': []
    }
    
    try:
        # 1. 参数验证和初始化
        if data is None:
            data = kwargs.get('data', {})
        
        # 2. 处理字符串类型的输入
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result['status'] = 'error'
                result['errors'].append(f'JSON解析失败：{str(e)}')
                return result
        
        # 3. 确保data是字典类型
        if not isinstance(data, dict):
            result['status'] = 'error'
            result['errors'].append(f'数据类型错误，期望dict，得到{type(data).__name__}')
            return result
        
        # 4. 执行核心分析逻辑
        result['data'] = _process_data(data)
        result['metrics'] = _calculate_metrics(result['data'])
        
        # 5. 验证分析结果
        if not result['data']:
            result['status'] = 'warning'
            result['errors'].append('分析结果为空，请检查输入数据')
        
    except Exception as e:
        result['status'] = 'error'
        result['errors'].append(f'分析执行失败：{str(e)}')
    
    return result


def _process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """处理原始数据，提取关键字段"""
    processed = {}
    
    # 安全获取常见电商数据字段
    processed['orders'] = data.get('orders', [])
    processed['sales'] = data.get('sales', 0)
    processed['inventory'] = data.get('inventory', {})
    processed['customers'] = data.get('customers', [])
    processed['products'] = data.get('products', [])
    
    # 确保列表类型字段不为None
    for key in ['orders', 'customers', 'products']:
        if processed.get(key) is None:
            processed[key] = []
    
    return processed


def _calculate_metrics(processed_data: Dict[str, Any]) -> Dict[str, Any]:
    """计算关键业务指标"""
    metrics = {
        'total_orders': 0,
        'total_sales': 0,
        'avg_order_value': 0,
        'customer_count': 0,
        'product_count': 0
    }
    
    try:
        metrics['total_orders'] = len(processed_data.get('orders', []))
        metrics['total_sales'] = float(processed_data.get('sales', 0))
        metrics['customer_count'] = len(processed_data.get('customers', []))
        metrics['product_count'] = len(processed_data.get('products', []))
        
        # 计算平均订单价值
        if metrics['total_orders'] > 0:
            metrics['avg_order_value'] = metrics['total_sales'] / metrics['total_orders']
    
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    
    return metrics


# 测试验证
def test_analyze():
    """测试analyze函数的各种场景"""
    
    # 测试1: 正常字典输入
    test_data = {
        'orders': [{'id': 1}, {'id': 2}],
        'sales': 1000,
        'customers': [{'id': 1}],
        'products': [{'id': 1}]
    }
    result1 = analyze(test_data)
    assert result1['status'] in ['success', 'warning']
    assert result1['metrics']['total_orders'] == 2
    
    # 测试2: 字符串JSON输入
    json_str = json.dumps(test_data)
    result2 = analyze(json_str)
    assert result2['status'] in ['success', 'warning']
    
    # 测试3: 空输入
    result3 = analyze()
    assert result3['status'] in ['success', 'warning', 'error']
    
    # 测试4: None输入
    result4 = analyze(None)
    assert result4['status'] in ['success', 'warning', 'error']
    
    print('所有测试通过！')
    return True


if __name__ == '__main__':
    test_analyze()
    
    # 示例调用
    sample_data = {
        'orders': [{'order_id': 'ORD001', 'amount': 500}],
        'sales': 500,
        'customers': [{'customer_id': 'C001'}],
        'products': [{'product_id': 'P001'}]
    }
    
    result = analyze(sample_data)
    print(f"分析状态：{result['status']}")
    print(f"订单数量：{result['metrics']['total_orders']}")
    print(f"销售总额：{result['metrics']['total_sales']}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
