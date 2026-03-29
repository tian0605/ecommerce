import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复了常见的analyze步骤执行失败问题
    """
    result = {
        'success': False,
        'data': None,
        'error': None,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # 1. 输入验证和初始化
        if data is None:
            data = {}
        
        # 2. 处理字符串类型的输入
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format: {str(e)}")
        
        # 3. 确保data是字典类型
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data).__name__}")
        
        # 4. 执行分析逻辑
        analysis_result = perform_analysis(data, **kwargs)
        
        # 5. 验证分析结果
        if analysis_result is None:
            raise ValueError("Analysis returned None result")
        
        # 6. 构建成功响应
        result['success'] = True
        result['data'] = analysis_result
        
        logger.info(f"Analyze completed successfully: {result['timestamp']}")
        
    except Exception as e:
        # 7. 异常处理和日志记录
        error_msg = f"{type(e).__name__}: {str(e)}"
        result['error'] = error_msg
        logger.error(f"Analyze failed: {error_msg}")
    
    return result


def perform_analysis(data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    执行实际的分析逻辑
    包含常见的电商数据分析操作
    """
    analysis = {
        'metrics': {},
        'summary': {},
        'recommendations': []
    }
    
    # 处理销售数据
    if 'sales' in data:
        sales_data = data['sales']
        if isinstance(sales_data, (int, float)):
            analysis['metrics']['total_sales'] = sales_data
        elif isinstance(sales_data, list):
            analysis['metrics']['total_sales'] = sum(sales_data)
            analysis['metrics']['avg_sales'] = sum(sales_data) / len(sales_data) if sales_data else 0
    
    # 处理订单数据
    if 'orders' in data:
        orders = data['orders']
        if isinstance(orders, (int, float)):
            analysis['metrics']['total_orders'] = orders
        elif isinstance(orders, list):
            analysis['metrics']['total_orders'] = len(orders)
    
    # 处理商品数据
    if 'products' in data:
        products = data['products']
        if isinstance(products, list):
            analysis['metrics']['product_count'] = len(products)
            analysis['summary']['top_products'] = products[:5] if len(products) >= 5 else products
    
    # 生成建议
    if analysis['metrics'].get('total_sales', 0) > 0:
        analysis['recommendations'].append('Sales performance is positive')
    
    if analysis['metrics'].get('total_orders', 0) == 0:
        analysis['recommendations'].append('No orders detected, check data source')
    
    return analysis


def test_analyze():
    """测试analyze函数"""
    # 测试1: 正常字典输入
    test_data1 = {
        'sales': [100, 200, 300],
        'orders': [1, 2, 3],
        'products': ['A', 'B', 'C', 'D', 'E']
    }
    result1 = analyze(test_data1)
    assert result1['success'] == True, "Test 1 failed"
    
    # 测试2: JSON字符串输入
    test_data2 = json.dumps({'sales': 500, 'orders': 10})
    result2 = analyze(test_data2)
    assert result2['success'] == True, "Test 2 failed"
    
    # 测试3: None输入
    result3 = analyze(None)
    assert result3['success'] == True, "Test 3 failed"
    
    # 测试4: 无效输入
    result4 = analyze("invalid json")
    assert result4['success'] == False, "Test 4 failed"
    
    print("All tests passed!")
    return True


if __name__ == '__main__':
    test_analyze()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
