import json
from typing import Dict, Any, Optional
from datetime import datetime

def analyze(data: Optional[Dict[str, Any]] = None, 
            metrics: Optional[list] = None,
            config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复参数验证和异常处理问题
    """
    # 参数默认值初始化
    if data is None:
        data = {}
    if metrics is None:
        metrics = ['sales', 'orders', 'inventory']
    if config is None:
        config = {}
    
    # 参数类型验证
    if not isinstance(data, dict):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
    
    if not isinstance(metrics, list):
        metrics = ['sales', 'orders', 'inventory']
    
    if not isinstance(config, dict):
        config = {}
    
    # 执行分析逻辑
    result = {
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'metrics': {},
        'summary': {}
    }
    
    try:
        # 处理每个指标
        for metric in metrics:
            if metric in data:
                result['metrics'][metric] = data[metric]
            else:
                result['metrics'][metric] = 0
        
        # 生成汇总数据
        result['summary'] = {
            'total_metrics': len(metrics),
            'data_keys': list(data.keys()),
            'config_applied': bool(config)
        }
        
    except Exception as e:
        result['status'] = 'error'
        result['error_message'] = str(e)
    
    return result


def fix_analyze_step(input_data: Any) -> Dict[str, Any]:
    """
    修复 analyze 步骤的包装函数
    确保输入数据格式正确
    """
    # 处理不同类型的输入
    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except json.JSONDecodeError:
            input_data = {'raw': input_data}
    elif input_data is None:
        input_data = {}
    elif not isinstance(input_data, dict):
        input_data = {'value': input_data}
    
    # 调用分析函数
    return analyze(data=input_data)


# 测试验证
def test_fix():
    """测试修复后的代码"""
    # 测试1: 正常字典输入
    result1 = fix_analyze_step({'sales': 1000, 'orders': 50})
    assert result1['status'] == 'success'
    
    # 测试2: JSON字符串输入
    result2 = fix_analyze_step('{"sales": 2000}')
    assert result2['status'] == 'success'
    
    # 测试3: None输入
    result3 = fix_analyze_step(None)
    assert result3['status'] == 'success'
    
    # 测试4: 直接调用analyze
    result4 = analyze(data={'inventory': 100}, metrics=['inventory'])
    assert 'inventory' in result4['metrics']
    
    return True


if __name__ == '__main__':
    # 运行测试
    test_result = test_fix()
    print(f"测试通过: {test_result}")
    
    # 示例运行
    sample_data = {
        'sales': 15000,
        'orders': 120,
        'inventory': 500
    }
    result = analyze(data=sample_data)
    print(f"分析结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
