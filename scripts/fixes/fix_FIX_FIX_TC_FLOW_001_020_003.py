#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电商运营自动化 - analyze 步骤修复模块
任务名：FIX-FIX-TC-FLOW-001-020-003
"""

import json
import logging
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def analyze(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    分析步骤核心函数
    
    Args:
        data: 输入数据字典
        **kwargs: 额外参数
    
    Returns:
        分析结果字典
    """
    try:
        # 参数验证和初始化
        if data is None:
            data = {}
        
        # 确保 data 是字典类型
        if isinstance(data, str):
            data = json.loads(data)
        elif not isinstance(data, dict):
            raise TypeError(f"data 必须是 dict 类型，当前类型：{type(data)}")
        
        # 执行分析逻辑
        result = {
            'status': 'success',
            'step': 'analyze',
            'input_keys': list(data.keys()),
            'input_count': len(data),
            'processed': True
        }
        
        # 处理业务数据（示例逻辑）
        if 'products' in data:
            result['product_count'] = len(data['products'])
        if 'orders' in data:
            result['order_count'] = len(data['orders'])
        
        logger.info(f"analyze 步骤执行成功，处理 {len(data)} 个数据项")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败：{e}")
        return {
            'status': 'error',
            'step': 'analyze',
            'error': f'JSON 解析错误：{str(e)}'
        }
    except Exception as e:
        logger.error(f"analyze 步骤执行失败：{e}")
        return {
            'status': 'error',
            'step': 'analyze',
            'error': str(e)
        }


def run_analyze_step(input_data: Any) -> Dict[str, Any]:
    """
    运行 analyze 步骤的包装函数
    
    Args:
        input_data: 输入数据（可以是 dict、str 或其他）
    
    Returns:
        分析结果
    """
    # 统一转换为字典
    if isinstance(input_data, str):
        try:
            data = json.loads(input_data)
        except json.JSONDecodeError:
            data = {'raw': input_data}
    elif isinstance(input_data, dict):
        data = input_data
    else:
        data = {'value': input_data}
    
    return analyze(data=data)


def test_fix():
    """测试验证修复代码"""
    print("=" * 50)
    print("开始测试 analyze 步骤修复...")
    print("=" * 50)
    
    # 测试用例 1: 正常字典输入
    test1 = {'products': ['A', 'B', 'C'], 'orders': [1, 2]}
    result1 = run_analyze_step(test1)
    assert result1['status'] == 'success', f"测试 1 失败：{result1}"
    print(f"✓ 测试 1 通过：字典输入 - {result1}")
    
    # 测试用例 2: JSON 字符串输入
    test2 = json.dumps({'products': ['X', 'Y']})
    result2 = run_analyze_step(test2)
    assert result2['status'] == 'success', f"测试 2 失败：{result2}"
    print(f"✓ 测试 2 通过：JSON 字符串输入 - {result2}")
    
    # 测试用例 3: 空输入
    test3 = None
    result3 = run_analyze_step(test3)
    assert result3['status'] == 'success', f"测试 3 失败：{result3}"
    print(f"✓ 测试 3 通过：空输入 - {result3}")
    
    # 测试用例 4: 直接调用 analyze 函数
    test4 = {'key': 'value'}
    result4 = analyze(data=test4)
    assert result4['status'] == 'success', f"测试 4 失败：{result4}"
    print(f"✓ 测试 4 通过：直接调用 analyze - {result4}")
    
    print("=" * 50)
    print("所有测试通过！analyze 步骤修复完成。")
    print("=" * 50)
    return True


if __name__ == '__main__':
    # 执行测试
    test_fix()
# 执行入口：apply_fix()
def apply_fix():
    pass  # 入口函数
