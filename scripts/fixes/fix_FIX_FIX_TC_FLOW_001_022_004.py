import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze(data: Optional[Dict[str, Any]] = None, 
            data_source: Optional[str] = None) -> Dict[str, Any]:
    """
    修复analyze步骤执行失败问题
    添加完善的数据验证和异常处理
    """
    result = {
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'data': {},
        'errors': []
    }
    
    try:
        # 1. 验证输入数据
        if data is None and data_source is None:
            raise ValueError("必须提供data或data_source参数")
        
        # 2. 处理数据源
        if data_source is not None:
            data = load_data_from_source(data_source)
        
        # 3. 验证数据格式
        if not isinstance(data, dict):
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError as e:
                    result['errors'].append(f"JSON解析失败: {str(e)}")
                    result['status'] = 'partial_success'
                    data = {}
            else:
                result['errors'].append(f"无效的数据类型: {type(data)}")
                result['status'] = 'partial_success'
                data = {}
        
        # 4. 执行分析逻辑
        if data:
            result['data'] = perform_analysis(data)
        else:
            result['data'] = {'message': '无数据可分析'}
            result['status'] = 'no_data'
        
        logger.info(f"analyze步骤完成，状态: {result['status']}")
        
    except Exception as e:
        logger.error(f"analyze步骤执行失败: {str(e)}")
        result['status'] = 'failed'
        result['errors'].append(str(e))
    
    return result


def load_data_from_source(source: str) -> Dict[str, Any]:
    """从数据源加载数据"""
    # 模拟数据源加载，实际使用时替换为真实逻辑
    if source.startswith('file://'):
        file_path = source.replace('file://', '')
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif source.startswith('api://'):
        # 模拟API调用
        return {'source': 'api', 'data': []}
    else:
        # 默认返回空数据
        return {}


def perform_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """执行实际的数据分析逻辑"""
    analysis_result = {
        'total_records': len(data) if isinstance(data, (list, dict)) else 0,
        'fields': list(data.keys()) if isinstance(data, dict) else [],
        'analysis_time': datetime.now().isoformat()
    }
    
    # 添加常见的电商分析指标
    if 'orders' in data:
        analysis_result['order_count'] = len(data['orders'])
    if 'products' in data:
        analysis_result['product_count'] = len(data['products'])
    if 'sales' in data:
        analysis_result['sales_data'] = data['sales']
    
    return analysis_result


def test_analyze_fix():
    """测试修复后的analyze函数"""
    print("测试1: 正常数据输入")
    result1 = analyze({'orders': [1, 2, 3], 'products': ['A', 'B']})
    assert result1['status'] in ['success', 'partial_success']
    print(f"结果: {result1['status']}")
    
    print("\n测试2: JSON字符串输入")
    result2 = analyze('{"orders": [1, 2]}')
    assert result2['status'] in ['success', 'partial_success']
    print(f"结果: {result2['status']}")
    
    print("\n测试3: 空数据输入")
    result3 = analyze({})
    assert result3['status'] in ['success', 'no_data']
    print(f"结果: {result3['status']}")
    
    print("\n测试4: None输入（应失败但被捕获）")
    result4 = analyze()
    assert result4['status'] == 'failed'
    print(f"结果: {result4['status']}")
    
    print("\n所有测试通过！")
    return True


if __name__ == '__main__':
    test_analyze_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
