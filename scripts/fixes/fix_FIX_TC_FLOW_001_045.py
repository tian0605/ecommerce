import json
from typing import Dict, Any, Optional

def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    电商运营数据分析函数
    修复常见的analyze步骤执行失败问题
    """
    result = {
        'status': 'success',
        'data': {},
        'message': '',
        'errors': []
    }
    
    try:
        # 1. 参数验证 - 处理None和空值
        if data is None:
            data = {}
        
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
        
        # 4. 执行分析逻辑
        analysis_data = {
            'total_items': len(data.get('items', [])),
            'total_amount': data.get('total_amount', 0),
            'order_count': data.get('order_count', 0),
            'analysis_time': None
        }
        
        # 5. 添加时间戳
        from datetime import datetime
        analysis_data['analysis_time'] = datetime.now().isoformat()
        
        # 6. 合并额外参数
        analysis_data.update(kwargs)
        
        result['data'] = analysis_data
        result['message'] = '分析完成'
        
    except Exception as e:
        result['status'] = 'error'
        result['errors'].append(f'分析执行异常：{str(e)}')
        result['message'] = '分析失败'
    
    return result


def fix_analyze_step(input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    修复analyze步骤的主函数
    包装analyze函数并提供额外的错误处理
    """
    try:
        # 调用修复后的analyze函数
        result = analyze(data=input_data)
        
        # 验证结果完整性
        if result.get('status') != 'success':
            # 记录错误但返回可用结果
            print(f"警告：analyze步骤存在错误 - {result.get('errors', [])}")
        
        return result
        
    except Exception as e:
        # 兜底错误处理
        return {
            'status': 'error',
            'data': {},
            'message': f'analyze步骤执行失败：{str(e)}',
            'errors': [str(e)]
        }


# 测试验证
def test_fix():
    """测试修复代码是否正常工作"""
    
    # 测试1：正常数据
    test_data = {
        'items': [{'id': 1}, {'id': 2}],
        'total_amount': 100.0,
        'order_count': 5
    }
    result1 = fix_analyze_step(test_data)
    assert result1['status'] == 'success', "测试1失败：正常数据应成功"
    
    # 测试2：空数据
    result2 = fix_analyze_step(None)
    assert result2['status'] == 'success', "测试2失败：空数据应成功"
    
    # 测试3：字符串数据
    result3 = fix_analyze_step('{"items": [], "total_amount": 0}')
    assert result3['status'] == 'success', "测试3失败：字符串数据应成功"
    
    # 测试4：无效JSON字符串
    result4 = fix_analyze_step('invalid json')
    assert result4['status'] == 'error', "测试4失败：无效JSON应报错"
    
    print("所有测试通过！")
    return True


if __name__ == '__main__':
    # 运行测试
    test_fix()
    
    # 示例使用
    sample_data = {
        'items': [{'sku': 'A001', 'qty': 10}],
        'total_amount': 999.99,
        'order_count': 1
    }
    result = fix_analyze_step(sample_data)
    print(f"分析结果：{json.dumps(result, ensure_ascii=False, indent=2)}")
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
